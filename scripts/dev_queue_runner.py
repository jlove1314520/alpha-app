# -*- coding: utf-8 -*-
"""開發佇列自走（2026-09-06 總司令「自走一」）。

**為什麼有這支**
開發工作今天停擺三次（02:36→07:06、12:33→19:20、22:19→…），每一次的原因都一樣：
互動視窗的工作階段一結束，正在進行的工作就沒有人接手。馬拉松那一軌不會這樣，
因為它是排程 + `claude -p` 無人值守跑的。這支把同一套機制搬到開發佇列上。

**這支自己不寫程式**——它負責讀佇列、判斷該不該停、產生提示詞、記錄結果；
真正動手的是 `run-dev-queue-cycle.ps1` 啟動的 `claude -p`，跟馬拉松同一個模式。

**停下條件（2026-09-18總司令裁示【改為連續自走】，取代原本這裡寫的
「三個停下條件」——權威版本現在是`CLAUDE.md`「零之一、停下條件改為
白名單」的七條，這裡列出的是這支腳本目前能自動偵測的子集，其餘三條
（解鎖holdout、真錢下單、佇列真空）由其他邏輯處理）**：
1. 需要總司令親自操作：登入授權、實機測試、花錢／採購、需要核准的裁示
2. 不可逆動作：刪資料、解鎖 holdout、真實下單
3. 要修改既有已驗證關卡的通過門檻（GATE1~6、violation_rate門檻等）
4. 法遵疑慮（ToS、爬蟲、付費資料、robots.txt）
5. 同一項連續失敗兩次

**「不確定但屬於可還原的技術選擇」不是停下理由**——選一個、寫下為什麼、
繼續做、回報裡標`[自行裁量]`，見`CLAUDE.md`零之一節。

停下時把原因寫進 PENDING_QUEUE 該項目並把它標成 `- [!]`（阻塞），下一輪就會跳過它
往下做——「結束該輪」不等於「從此卡在這一項」，那會變成總司令說的空轉。

用法：
    python scripts/dev_queue_runner.py next            # 印出下一個待辦（給人看的）
    python scripts/dev_queue_runner.py check_collision # 這一輪該不該讓路（見下方說明）
    python scripts/dev_queue_runner.py prompt          # 產生本輪提示詞到 research/DEV_QUEUE_PROMPT.txt
    python scripts/dev_queue_runner.py block "原因"    # 把目前這一項標成阻塞並寫入原因
    python scripts/dev_queue_runner.py fail            # 記一次失敗（連兩次會自動 block）
    python scripts/dev_queue_runner.py ok              # 清掉該項的失敗計數

**碰撞防呆（check_collision，2026-09-10 重開機復原.第二輪新增）**
以前 wrapper（`run-dev-queue-cycle.ps1`）自己用「工作目錄乾不乾淨」判斷
該不該讓路，先後踩過兩種死結：(1) 機器寫檔案（data/*.json、各種.log/.jsonl）
永遠讓樹是髒的 → 改白名單排除；(2) 白名單排除機器寫檔後，一輪自走行程中途
被中斷（rate limit／重開機／斷網）留下的**真實但沒人在管的殘局檔案**，
會被永遠誤判成「有人正在中途」而卡死到有人手動介入。`check_collision()`
兩層都查：別的自走軌道（marathon／hypothesis_queue）的鎖是否新鮮＝真的在跑；
排除機器寫檔後剩下的未提交變更，是否有檔案在最近`COLLISION_RECENCY_MINUTES`
分鐘內被改過＝有人（含互動視窗）現在真的在動手。兩者都沒有，就判定剩下的
髒是陳舊殘局，不再阻擋。判斷邏輯全部在這支檔案，`run-dev-queue-cycle.ps1`
只呼叫、不自己判斷，方便版本控制與稽核。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 2026-09-19（總司令裁示【最優先·三個都是總司令自己造成的故障】一）：Windows
# 主控台預設cp950編不出🔲（U+1F532）這類emoji，本檔`STALE_STATUS_MARKERS`
# 偵測到它時會print含這個字的字串，UnicodeEncodeError會讓整支runner崩潰、
# exit=1，`run-dev-queue-cycle.ps1`收到非預期退出碼變成crash-loop（每輪
# 重跑又再次崩潰）。跟`scripts/probe_twse_publish_time.py`已驗證過的同一套
# 修法：強制stdout/stderr用utf-8、編不出的字元用replace頂替，不讓輸出編碼
# 問題有機會變成整支腳本的當機原因。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "PENDING_QUEUE.md"
STATE = ROOT / "research" / "data" / "dev_queue_state.json"
PROMPT_OUT = ROOT / "research" / "DEV_QUEUE_PROMPT.txt"
TZ = timezone(timedelta(hours=8))
MAX_CONSECUTIVE_FAILS = 2

sys.path.insert(0, str(ROOT / "research"))
import marathon_lock  # noqa: E402 -- 同目錄下的鎖工具，重用它的鎖檔格式與陳舊門檻判斷
from queue_depth_config import MIN_QUEUE_DEPTH, TARGET_QUEUE_DEPTH  # noqa: E402 -- 單一事實來源，2026-09-20裁示【Q4前視與#23無法重現】四

# 2026-09-10（重開機復原.第二輪，總司令裁示「修機制不是手收尾」）：
# 舊版防呆（曾經在 run-dev-queue-cycle.ps1 裡）是「工作目錄乾淨才動手」，
# 12:42 那次改成白名單排除機器寫檔，但當天 15:01/18:16/21:46 三次證明白名單
# 不夠——**一輪自走行程中途被中斷（rate limit／重開機／斷網）會留下未commit
# 的真實檔案改動**，那個檔案不在白名單裡（例如 research/update_strategy_
# performance.py、.github/scripts/news_body_extract.py），於是自走佇列永遠
# 把「已經沒有人在動的殘局」誤判成「有人正在中途」，卡死到有人手動介入為止。
# 總司令裁示要用鎖當碰撞訊號，不要看樹髒不髒。新設計兩層都要通過才放行：
#   1) marathon／hypothesis_queue 這兩條**其他**自走軌道目前是否持有新鮮的鎖
#      （用它們各自的陳舊門檻判斷，不是我自己編一個）——這條抓「另一個自走
#      行程現在真的在跑」，跟devqueue自己的.devqueue.lock是同一套機制、只是
#      檢查別人的鎖不是自己的。
#   2) 排除機器寫檔案後，剩下的未提交變更裡，有沒有檔案是「最近
#      COLLISION_RECENCY_MINUTES 分鐘內」被改過——這條抓「有人（含互動視窗）
#      現在真的在手動改東西」，不需要那個人另外去搶一把鎖才算數。
#      超過這個時間還沒人碰的未提交變更，判定為某條軌道中斷後留下的殘局，
#      不再視為碰撞訊號——這正是舊版永遠卡死的根因：從來沒有「多舊算陳舊」
#      這個概念，任何一個字元的差異都無限期擋住整條自走線。
COLLISION_RECENCY_MINUTES = 20  # 略大於devqueue自己15分鐘的排程間隔，留一點餘裕
OTHER_TRACKS = ("marathon", "hypothesis_queue")  # devqueue自己的鎖由wrapper另外處理，不在這裡查
MACHINE_WRITTEN = [
    re.compile(r"^data/"),                    # 全部是排程產生的資料檔
    re.compile(r"^research/[^/]+\.log$"),     # 各 cycle 的執行日誌
    re.compile(r"^research/[^/]+\.jsonl$"),   # append-only 觀測紀錄
    re.compile(r"^research/\.[^/]+$"),        # .pid / .lock / .*_state.json 等隱藏狀態檔
    re.compile(r"^research/DEV_QUEUE_PROMPT\.txt$"),  # 本專案每輪重寫的提示檔
]


def _other_track_lock_reason() -> str | None:
    """有沒有『別人』（marathon／hypothesis_queue）的鎖現在是新鮮的。"""
    for name in OTHER_TRACKS:
        lock_path = marathon_lock._lock_path(name)
        if not lock_path.exists():
            continue
        _pid, ts, cycle_id = marathon_lock._read_lock(lock_path)
        if ts == 0:
            continue
        age_min = (time.time() - ts) / 60.0
        if age_min < marathon_lock._stale_minutes_for(name):
            return f"{name}軌道的鎖仍新鮮（cycle_id={cycle_id}，{age_min:.1f}分鐘前取得），判定它正在跑，本輪讓路"
    return None


def _recent_real_dirty_reason() -> str | None:
    """排除機器寫檔後，剩下的未提交變更裡有沒有『最近』被改過的檔案。"""
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), "status", "--porcelain"],
            capture_output=True, text=True, check=True, encoding="utf-8",
        ).stdout
    except (subprocess.CalledProcessError, OSError) as e:
        return f"git status 執行失敗（{e}），保守起見本輪讓路"
    now = time.time()
    hits = []
    for line in out.splitlines():
        if not line or line.startswith("??"):  # untracked 不算，跟白名單邏輯一致
            continue
        path = line[3:]  # porcelain 是「2碼狀態+1空格+路徑」
        if any(p.match(path) for p in MACHINE_WRITTEN):
            continue
        try:
            age_min = (now - (ROOT / path).stat().st_mtime) / 60.0
        except OSError:
            continue  # 檔案已被刪除等邊界情況，不當成碰撞訊號
        if age_min < COLLISION_RECENCY_MINUTES:
            hits.append(f"{path}（{age_min:.1f}分鐘前）")
    if hits:
        return f"有非機器寫入的檔案在最近{COLLISION_RECENCY_MINUTES}分鐘內被改動：{'、'.join(hits)}，判定有人正在中途，本輪讓路"
    return None


def check_collision() -> int:
    """給 wrapper 呼叫的唯一入口。exit 0＝可以繼續，exit 1＝本輪該讓路。

    判斷邏輯全部在這支檔案裡（版本控制、可稽核），wrapper 只負責呼叫與印 log。
    """
    reason = _other_track_lock_reason() or _recent_real_dirty_reason()
    if reason:
        print(f"YIELD: {reason}")
        return 1
    print("PROCEED: 沒有其他軌道持鎖中，也沒有最近被改動的非機器寫入檔案")
    return 0

# 2026-09-18（總司令裁示【改為連續自走】）：這幾個regex對應CLAUDE.md
# 「零之一、停下條件改為白名單」七條裡機器可以事先偵測的幾條（2需總司令
# 親自操作、3解鎖holdout、4真錢下單、5改GATE門檻、6法遵疑慮）——寧可
# 誤判成「要停」也不要讓無人值守的行程去點登入、花錢、悄悄調鬆驗證門檻、
# 或做出法遵有疑慮的事。條件1（花錢/不可逆）與條件7（佇列真空）由其他
# 邏輯處理，不在這裡。
NEEDS_USER = re.compile(
    r"登入|授權|實機|親自|購買|採購|付費|花錢|信用卡|核准|裁示|截圖給|公司手機|"
    r"手動貼|貼給總司令|請總司令|等總司令")
IRREVERSIBLE = re.compile(
    r"刪除|清空|holdout|真實下單|下單 API|不可逆|覆蓋.*資料庫|"
    r"調鬆.*門檻|放寬.*門檻|改.*GATE\d|修改.*通過門檻|violation_rate門檻|"
    r"ToS|robots\.txt|服務條款|繞過驗證碼|付費資料|爬蟲.*繞")


def _load_state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(d: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def _lines() -> list[str]:
    return QUEUE.read_text(encoding="utf-8").splitlines()


# 2026-09-18（Cowork【重構.B收成前必修】順手修）：舊標記是裸字
# "ORDER-BEGIN"/"ORDER-END"，會被裁示原文引用/執行記錄裡的同一串文字
# 撞到——實測當時檔案裡已經有4次"ORDER-BEGIN"、1次"ORDER-END"，
# split("ORDER-BEGIN", 1)取第一次出現，解析出3578筆垃圾項目，真正的
# 清單完全讀不到，只是「垃圾對不上by_key就退回檔案順序」這個既有防呆
# 沒讓它出事，權威排序清單本身早就是死的。改用HTML註解格式**且要求
# 必須整行只有這個標記**（用`ln.strip() == marker`比對，不是`in`子字串
# 比對）——這支撐得住連自己都不小心中招的情況：登記這次裁示原文時，
# 因為裁示原文本身就示範了`<!-- ORDER-BEGIN -->`這串文字當例子、加上
# 執行記錄裡也提到它，檔案裡一度又出現了3次`<!-- ORDER-BEGIN -->`
# 子字串（2次在散文/引言裡、1次是真正的標記），若只做子字串計數會
# 對自己的修復觸發假警報。改成「整行只有標記本身」才算數之後，
# 散文裡提到這個字串（不管在引言、程式碼區塊說明或反引號裡）都不會
# 被誤判，只有真正獨立成行的標記才算——這比要求「以後寫文件時永遠
# 記得不要完整拼出這串字」更可靠，因為後者已經連續失守兩次。
ORDER_BEGIN_MARKER = "<!-- ORDER-BEGIN -->"
ORDER_END_MARKER = "<!-- ORDER-END -->"


def _order_marker_line_indices(marker: str, lines: list[str]) -> list[int]:
    """回傳哪幾行「整行去除頭尾空白後」剛好等於marker本身，不含在其他文字裡的提及。"""
    return [i for i, ln in enumerate(lines) if ln.strip() == marker]


def _order_marker_ambiguity() -> str | None:
    """標記各自以獨立行出現的次數是否不是「剛好一組」。回傳問題描述，沒問題回None。"""
    lines = _lines()
    n_begin = len(_order_marker_line_indices(ORDER_BEGIN_MARKER, lines))
    n_end = len(_order_marker_line_indices(ORDER_END_MARKER, lines))
    if n_begin == 1 and n_end == 1:
        return None
    return (f"{ORDER_BEGIN_MARKER}以獨立行出現{n_begin}次、"
            f"{ORDER_END_MARKER}以獨立行出現{n_end}次，預期各恰好1次")


def _explicit_order() -> list[str]:
    """讀 PENDING_QUEUE 頂端 ORDER-BEGIN/ORDER-END 之間的權威執行順序。

    2026-09-07（轉向裁示）加入：總司令重排了佇列，但用「搬動區塊」來表達順序有兩個
    問題——大檔搬動容易改壞，而且會讓「原話全文」的區塊失去時間脈絡。改成在頂端維護
    一份項目編號清單，要調順序只改那份清單。清單不存在時就回退到檔案順序，
    所以這個機制壞掉最多是回到舊行為，不會讓 runner 停擺。

    2026-09-18新增：只認「整行剛好等於標記」的行（見`_order_marker_line_indices()`），
    不是子字串比對，散文提及不會誤觸。標記出現不只一組時，不能默默選一個將就
    用——取「最後一個開始標記」+「開始標記之後第一個結束標記」只是雙重防呆的
    第二層，第一層是呼叫端（`build_prompt()`）要用`_order_marker_ambiguity()`
    檢查並記`QUEUE_ORDER_MARKER_AMBIGUOUS`，不是這支函式自己默默決定用哪一組。
    """
    lines = _lines()
    begins = _order_marker_line_indices(ORDER_BEGIN_MARKER, lines)
    ends = _order_marker_line_indices(ORDER_END_MARKER, lines)
    if not begins or not ends:
        return []
    begin_idx = begins[-1]
    end_candidates = [e for e in ends if e > begin_idx]
    if not end_candidates:
        return []
    end_idx = end_candidates[0]
    return [ln.strip() for ln in lines[begin_idx + 1:end_idx] if ln.strip()]


def find_next() -> tuple[int, str] | None:
    """回傳 (行號, 該行文字)，找不到回 None。只認 `- [ ]` 開頭、跳過 `- [!]`。

    優先依頂端的權威順序清單取件；清單裡的項目都做完（或都被標成阻塞）之後，
    再回到檔案順序處理剩下的。**`[研究]` 類項目一律跳過**（2026-09-18新增，
    見下方迴圈內註解）——這支只服務 DevQueue（開發帽），研究類工作交給
    marathon／hypothesis_queue 讀同一份檔案自己接手，回 None 不代表沒有
    任何待辦，只代表「沒有輪到 DevQueue 做的」，呼叫端要用
    `_has_any_pending_line()` 分辨這兩種情況。
    """
    lines = _lines()
    pending = [(i, ln) for i, ln in enumerate(lines) if ln.startswith("- [ ]")]
    if not pending:
        return None
    order_entries = _explicit_order()
    if order_entries:
        by_key = {}
        for i, ln in pending:
            by_key.setdefault(item_key(ln), (i, ln))
        # 2026-09-07（總司令裁示 2）公平規則：連續派出兩項 [債務] 之後，
        # 下一項必須派 [產品]。理由寫在 PENDING_QUEUE 標頭——債務工作永遠有正當
        # 理由插隊，結果 建置一.1 從 9/5 核准到 9/7 一次都沒開始過。
        st = _load_state()
        recent = st.get("_recent_classes", [])
        need_product = len(recent) >= 2 and all(x == "債務" for x in recent[-2:])
        ordered = [_entry_key_class(k) for k in order_entries]
        if need_product:
            for key, cls in ordered:
                if cls == "產品" and key in by_key:
                    return by_key[key]
            # 沒有產品類可派就照原順序走，但把計數清掉，免得下一輪還在等一個
            # 永遠不會出現的產品項（那會變成另一種卡住）
            st["_recent_classes"] = []
            _save_state(st)
        for key, cls in ordered:
            # 2026-09-18（總司令裁示【改為多軌並行】的落地）：[研究]類項目屬於
            # marathon／hypothesis_queue軌，不是DevQueue（開發帽）的工作——見
            # CLAUDE.md九、帽子規則「越權禁止」。過去曾經因為ORDER清單機械式
            # 取件不分track，把#74這類研究工作錯派給DevQueue（見PENDING_QUEUE.md
            # 2026-09-16該筆⛔記錄），這裡直接跳過，讓它留給對的track去讀
            # PENDING_QUEUE.md（那些track是`claude -p`提示詞讀全文判斷，不靠
            # 這支腳本的機械式解析，所以跳過不影響它們看得到這一項）。
            if cls == "研究":
                continue
            if key in by_key:
                return by_key[key]
    # 走到這裡代表：沒有ORDER清單、或清單裡沒有一項能在pending裡對上——
    # 兩種情況都退回檔案順序，但一樣要濾掉[研究]類項目（用item_class()判斷，
    # 邏輯與上面ordered分支一致，只是這裡沒有現成的cls可用）。
    non_research = [(i, ln) for i, ln in pending if item_class(ln) != "研究"]
    return non_research[0] if non_research else None


def _entry_key_class(entry: str) -> tuple[str, str]:
    """把 ORDER-BEGIN 清單裡一行拆成 (項目編號key, 類別)。類別看 [產品]/[研究] 標記，都沒有就是債務。"""
    if "[研究]" in entry:
        return entry.replace("[研究]", "").strip(), "研究"
    if "[產品]" in entry:
        return entry.replace("[產品]", "").strip(), "產品"
    return entry.strip(), "債務"


INLINE_CLASS_TAG = re.compile(r"\*\*[^*]+\*\*\s*(\[研究\]|\[產品\])")


def item_class(text: str) -> str:
    """這一項是債務、產品還是研究。

    2026-09-23（本輪DevQueue自走發現的分類漏洞修復）：舊版只用ORDER清單的key
    做比對，但ORDER清單的key有時是「父項代號」（例如`驗.一`），而實際佇列裡
    的子項行卻用了更長的代號（例如`驗.一第4點續（剩餘16支）`）——兩者字串
    不相等，`_explicit_order()`比對不到，就會默默退回預設值「債務」，即使
    那一行**自己的文字裡就明寫著`[研究]`標記**。這正是CLAUDE.md「十二」節
    講的同一種形狀：分類邏輯的前提（key會完全對應）隨佇列內容變複雜而不再
    成立，而且失效方向是「研究工作被誤判成債務、派給不該做研究判定的
    DevQueue」，不是「完全不動作」，更難被發現——本次是靠實際執行
    `find_next()`才抓到`驗.一第4點續（剩餘16支）`被誤判派工。
    修法：優先信任這一行文字自己緊跟在`**代號**`之後的`[研究]`/`[產品]`
    標記（如果有），比對不到才退回ORDER清單比對，兩層都沒有才預設債務。
    """
    m = INLINE_CLASS_TAG.search(text)
    if m:
        return "研究" if m.group(1) == "[研究]" else "產品"
    key = item_key(text)
    for entry in _explicit_order():
        entry_key, cls = _entry_key_class(entry)
        if entry_key == key:
            return cls
    return "債務"


def _note_dispatch(text: str) -> None:
    """記下這一輪派出的是哪一類，供公平規則判斷。只留最近 6 筆。"""
    st = _load_state()
    recent = st.get("_recent_classes", [])
    recent.append(item_class(text))
    st["_recent_classes"] = recent[-6:]
    _save_state(st)


def item_key(text: str) -> str:
    """用項目編號當 key（例如 **建置一.1**）。取不到就用整行前 60 字。"""
    m = re.search(r"\*\*([^*]+)\*\*", text)
    return m.group(1).strip() if m else text[:60].strip()


def mark_blocked(reason: str) -> int:
    nxt = find_next()
    if nxt is None:
        print("NO_ITEM")
        return 1
    idx, text = nxt
    lines = _lines()
    stamp = datetime.now(TZ).strftime("%Y-%m-%d %H:%M")
    lines[idx] = (text.replace("- [ ]", "- [!]", 1)
                  + f"　**⛔ 自走中止（{stamp}）**：{reason}")
    QUEUE.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    st = _load_state()
    st.pop(item_key(text), None)
    _save_state(st)
    print(f"BLOCKED: {item_key(text)} — {reason}")
    return 0


def record(result: str) -> int:
    nxt = find_next()
    if nxt is None:
        print("NO_ITEM")
        return 0
    _, text = nxt
    key = item_key(text)
    st = _load_state()
    if result == "ok":
        st.pop(key, None)
        _save_state(st)
        print(f"OK: {key} 失敗計數已清除")
        return 0
    entry = st.setdefault(key, {"fails": 0})
    entry["fails"] += 1
    entry["last_at"] = datetime.now(TZ).isoformat()
    _save_state(st)
    print(f"FAIL: {key} 連續失敗 {entry['fails']} 次")
    if entry["fails"] >= MAX_CONSECUTIVE_FAILS:
        return mark_blocked(f"連續 {entry['fails']} 次失敗，需要總司令看一眼再決定怎麼走")
    return 0


# 2026-09-18（總司令裁示【最優先·修理自走系統】）矛盾偵測：find_next()回None
# 不代表「真的沒事做」——2026-09-08~09-18這段期間PENDING_QUEUE.md累積209筆
# 用散文+🔲記錄的裁示，但「- [ ]」開頭的行數是0，導致DevQueue每輪誤判成
# QUEUE_EMPTY安靜睡回去，實際上待辦一直都在，只是換了個機器認不得的格式。
STALE_STATUS_MARKERS = re.compile(r"🔲|進行中|未開始")


def _has_any_pending_line() -> bool:
    """檔案裡是否還有任何「- [ ]」開頭的行，不分產品/債務/研究。"""
    return any(ln.startswith("- [ ]") for ln in _lines())


def _stale_status_markers_present() -> bool:
    """檔案原文（不只是「- [ ]」那幾行）裡是否還留著🔲／進行中／未開始這類散文狀態字樣。

    2026-09-19（總司令裁示【最優先·三個都是總司令自己造成的故障】三，發現
    這支自己也踩到新硬規則要防的那種故障）：這支2026-09-18才新增，設計
    時假設「檔案裡幾乎沒有`- [x]`/`- [!]`，卻大量出現🔲/進行中/未開始」
    才代表真的漏抓。但實測（2026-09-19，檔案已成長到8千多行）這個假設已
    失效——`進行中`／`未開始`是極常見的中文敘述用詞（例如「佇列還剩幾條
    未開始」這種例行回報句型），單純字串比對在歷史行文裡永遠會撞到，
    跟`- [ ]`格式有沒有被正確使用完全無關。實測全檔含這三個字樣的比對
    命中68次，扣掉附近有「已完成/✅/已於commit」等解決字樣的38次，剩下
    30次逐一核對**全部是歷史敘述或既有裁示的引文，沒有一個是真的漏抓**。
    這個函式本身回傳值因此不再可信（見`build_prompt()`呼叫端如何處理），
    保留字串比對邏輯本身只是留給未來設計更精準版本時參考，不代表現在
    這個True/False有直接拿來當警報的資格。
    """
    return bool(STALE_STATUS_MARKERS.search(QUEUE.read_text(encoding="utf-8")))


def _checkbox_convention_actively_used() -> bool:
    """`- [x]`／`- [!]`兩種收尾標記加總是否有一定數量——用來判斷「機器可讀
    checkbox格式現在到底有沒有在用」，這是`_stale_status_markers_present()`
    當年（2026-09-18）想偵測的真正問題（「近期裁示全部繞過checkbox格式」），
    比直接對散文字串比對可靠很多：checkbox格式只要還在被積極使用，散文
    裡出現🔲/進行中/未開始這幾個字就高機率只是歷史敘述，不是真的漏抓。
    門檻5是保守值，不是精算出來的——當年出事時是「0個- [ ]、209個- [x]」
    這種checkbox本身有在長期使用、只是新裁示沒跟上格式的狀況，5遠低於
    209，寧可門檻低一點也不要漏抓真正的格式崩壞（checkbox整個沒人用）。
    """
    n = sum(1 for ln in _lines() if ln.startswith("- [x]") or ln.startswith("- [!]"))
    return n >= 5


def _record_format_mismatch(detail: str) -> None:
    st = _load_state()
    st["_format_mismatch"] = {"detected_at": datetime.now(TZ).isoformat(), "detail": detail}
    _save_state(st)


def _clear_format_mismatch() -> None:
    st = _load_state()
    if st.pop("_format_mismatch", None) is not None:
        _save_state(st)


def get_format_mismatch_alerts() -> list[str]:
    """給 `check_external_connectivity.py` 呼叫（2026-09-18 重構.E1）：
    `_format_mismatch` 旗標存在時回傳一則告警文字，讓它併進 `local_task_health`
    的 `stalled` 清單、真的能讓 `AlphaDevQueue` 亮燈，不再只印在
    `dev_queue_cycle.log` 裡等人翻。這支只讀狀態檔，不清旗標——旗標的生命週期
    完全由 `build_prompt()` 自己管理（判定成真的做完／讓路給[研究]類時會呼叫
    `_clear_format_mismatch()` 清掉，這裡不重複那份邏輯）。
    """
    st = _load_state()
    info = st.get("_format_mismatch")
    if not info:
        return []
    detected_at = info.get("detected_at", "未知時間")
    detail = info.get("detail", "（無詳細訊息）")
    return [f"DevQueue 佇列格式不符（自 {detected_at} 起未解除）：{detail}"]


def _safe_print(msg: str) -> None:
    """任何print()都可能因主控台編碼問題丟例外（2026-09-19教訓：cp950印不出
    🔲讓整支runner崩潰、crash-loop三小時）。這支保證「印一行訊息」這件事
    本身不會拋例外中斷呼叫端——先試正常print()（模組頂端已reconfigure成
    utf-8，正常情況這裡就會成功），失敗就退化印ASCII安全版本，兩次都失敗
    也吞掉，絕不讓輸出動作本身變成流程中斷的原因。"""
    try:
        print(msg)
    except Exception:  # noqa: BLE001
        try:
            print(msg.encode("ascii", errors="backslashreplace").decode("ascii"))
        except Exception:  # noqa: BLE001
            pass


_LINE_TAG = re.compile(r"^- \[ \]\s*\*\*[^*]+\*\*\s*\[(研究|產品|債務|驗證)\]")


def _line_class(text: str) -> str | None:
    """項目行自己在`**編號**`後面標的類別（[研究]/[產品]，[債務]/[驗證]/沒標都歸債務類，
    跟`_entry_key_class`只認研究/產品的口徑一致）。項目行根本沒標籤回None（不做比對）。"""
    m = _LINE_TAG.match(text)
    if not m:
        return None
    return m.group(1) if m.group(1) in ("研究", "產品") else "債務"


def order_tag_mismatches() -> list[str]:
    """2026-09-20（稽核.六續二）：找出「ORDER清單條目的類別 ≠ 項目行自己標的類別」。
    起因：`原子.六`項目行是[研究]、ORDER清單條目卻沒帶[研究]，find_next()因此把研究項目派給了
    DevQueue（已手動補標籤）。只報不改檔。

    2026-09-23（本輪DevQueue自走修復`item_class()`後更新）：「項目行標[研究]但不在
    ORDER清單」這個分支原本會警告「item_class會當債務派給DevQueue」，但`item_class()`
    現在優先信任項目行自己的inline標記（見該函式docstring），這種情形已經自動修正、
    不會再誤派——只有「ORDER清單裡有這個key、但標的類別跟項目行自己標的不一樣」才是
    需要人工核對的真矛盾（可能是ORDER清單筆誤，也可能是項目行筆誤，兩者哪個對需要
    看裁示原文），保留這一種警告即可。"""
    lines = _lines()
    order = {}
    for entry in _explicit_order():
        key, cls = _entry_key_class(entry)
        order[key] = cls
    out = []
    for ln in lines:
        if not ln.startswith("- [ ]"):
            continue
        line_cls = _line_class(ln)
        if line_cls is None:
            continue
        key = item_key(ln)
        if key in order and order[key] != line_cls:
            out.append(f"{key}: ORDER清單標{order[key]}、項目行標{line_cls}")
    return out


def _report_order_tag_mismatches() -> None:
    """守門員自身失敗只降級成警告（CLAUDE.md十二節）：偵測到不一致只印WARN，
    偵測邏輯本身丟例外也只印WARN_DETECTOR_CRASHED，絕不影響build_prompt的回傳碼。"""
    try:
        for m in order_tag_mismatches():
            _safe_print(f"WARN_ORDER_TAG_MISMATCH: {m}")
    except Exception as e:  # noqa: BLE001
        _safe_print(f"WARN_DETECTOR_CRASHED: order_tag_mismatches failed ({type(e).__name__}), skipped this round")


def build_prompt() -> int:
    # 2026-09-19（總司令裁示【最優先·三個都是總司令自己造成的故障】一.2）：
    # 這整段矛盾偵測（含2026-09-18加的ORDER-BEGIN檢查）包一層try/except——
    # 新硬規則「任何偵測器/守門員自身失敗只能降級成一行警告，絕不得讓被
    # 監控的流程非零退出或中斷」（見CLAUDE.md對應章節）。這裡"crash"指的是
    # 偵測邏輯本身丟出未預期例外（例如未來又有別的編碼/正規表達式/檔案IO
    # 問題），不是「偵測到真的矛盾」這種設計內的return 4/5——那些是正常
    # 工作結果，不是本規則要防的對象。偵測失敗一律fail open（當成沒偵測到
    # 問題），因為「這輪漏抓一次矛盾」永遠比「DevQueue整支崩潰3小時」代價低。
    ambiguity = None
    try:
        ambiguity = _order_marker_ambiguity()
    except Exception as e:  # noqa: BLE001
        _safe_print(f"WARN_DETECTOR_CRASHED: order_marker_ambiguity check failed "
                     f"({type(e).__name__}), treating as no ambiguity this round")
    if ambiguity:
        try:
            detail = f"QUEUE_ORDER_MARKER_AMBIGUOUS: {ambiguity}"
            _record_format_mismatch(detail)
            PROMPT_OUT.write_text("NO_PENDING_ITEM", encoding="utf-8")
            _safe_print(detail)
        except Exception as e:  # noqa: BLE001
            _safe_print(f"WARN_DETECTOR_CRASHED: reporting order marker ambiguity "
                         f"failed ({type(e).__name__})")
        return 5
    _report_order_tag_mismatches()
    nxt = find_next()
    if nxt is None:
        PROMPT_OUT.write_text("NO_PENDING_ITEM", encoding="utf-8")
        if _has_any_pending_line():
            # 還有「- [ ]」項目，只是全部是[研究]類（不歸DevQueue管）——這是
            # 正常讓路，不是矛盾。清掉舊的mismatch旗標（狀態已經自癒）。
            _clear_format_mismatch()
            _safe_print("NO_PENDING_ITEM_FOR_DEVQUEUE：剩餘待辦皆為[研究]類，留給"
                         "marathon／hypothesis_queue軌")
            return 3
        stale = False
        try:
            stale = _stale_status_markers_present()
        except Exception as e:  # noqa: BLE001
            _safe_print(f"WARN_DETECTOR_CRASHED: stale_status_markers check failed "
                         f"({type(e).__name__}), treating as false this round")
        # 2026-09-19：只有「散文裡有這些字樣」還不夠，還要checkbox格式本身
        # 不活躍（見_checkbox_convention_actively_used()docstring）兩者同時
        # 成立，才判定為真的格式崩壞——單靠字串比對已證實在長檔案裡100%
        # 假陽性（歷史敘述永遠會撞到「進行中」「未開始」這幾個常用詞）。
        # 只有stale=True但checkbox格式仍活躍時，降級成資訊性紀錄，不觸發
        # 會進local_task_health的alert，避免「偵測器自己一直在喊狼來了」
        # 反而蓋掉真正的格式崩壞警報（跟新硬規則同一種精神：偵測器不可靠
        # 時寧可少報，不能讓它的雜訊癱瘓下游判斷）。
        convention_active = True
        try:
            convention_active = _checkbox_convention_actively_used()
        except Exception as e:  # noqa: BLE001
            _safe_print(f"WARN_DETECTOR_CRASHED: checkbox_convention check failed "
                         f"({type(e).__name__}), treating as active this round")
        if stale and not convention_active:
            try:
                detail = ("find_next()回None但檔案仍有🔲/進行中/未開始字樣、且"
                           "checkbox格式(- [x]/- [!])本身用量過低，判定為格式不符而非真的做完")
                _record_format_mismatch(detail)
                _safe_print(f"QUEUE_FORMAT_MISMATCH: {detail}")
            except Exception as e:  # noqa: BLE001
                _safe_print(f"WARN_DETECTOR_CRASHED: reporting format mismatch "
                             f"failed ({type(e).__name__})")
            return 4
        if stale:
            _safe_print("INFO: 散文裡仍有🔲/進行中/未開始字樣，但checkbox格式本身"
                         "活躍使用中，判定為歷史敘述殘留，不觸發格式不符警報"
                         "（2026-09-19修法，見_stale_status_markers_present()docstring）")
        _clear_format_mismatch()
        _safe_print("NO_PENDING_ITEM")
        return 3
    _clear_format_mismatch()
    _, text = nxt
    key = item_key(text)
    clean = re.sub(r"^- \[ \]\s*", "", text).strip()

    # 停下條件 1、2 在產生提示詞之前就先判斷——不要讓無人值守的行程「開始做了才發現不能做」
    if NEEDS_USER.search(clean):
        mark_blocked("需要總司令親自操作（登入／實機／花錢／核准），自走行程不做這類事")
        print("BLOCKED_NEEDS_USER")
        return 2
    if IRREVERSIBLE.search(clean):
        mark_blocked("涉及不可逆動作，依 CLAUDE.md 必須先問過總司令")
        print("BLOCKED_IRREVERSIBLE")
        return 2

    st = _load_state()
    fails = st.get(key, {}).get("fails", 0)
    prev = f"\n注意：這一項已經連續失敗 {fails} 次。再失敗一次就會被標成阻塞交給總司令，" \
           f"所以這一輪先把「為什麼失敗」查清楚再動手。\n" if fails else ""
    cycle_id = os.environ.get("ALPHA_CYCLE_ID", "unknown")

    prompt = f"""全程繁體中文。你是 Alpha 專案的開發佇列自走輪次（無人值守，沒有人在旁邊看）。
這一輪的 cycle_id 是 `{cycle_id}`（這是實際值，不是佔位符，直接照抄）。

## 這一輪要做的事
`C:\\alpha\\alpha-app\\PENDING_QUEUE.md` 頂端「執行順序（權威清單）」取到的下一項：

    {clean}
{prev}
做完這一項就接著做權威清單裡的下一項，**一輪之內連續做多項，做到不能再做為止**
（額度節流／所有項目都BLOCKED／碰到下面的停下條件才結束這一輪），不是做完一項
就結束。**一次做一項，每一項各自commit**，不要把好幾項混在同一個 commit 裡。

## 開工前先做兩件事（2026-09-18總司令裁示【改為連續自走】新增）
1. **檢查已標`- [!]`的阻塞項有沒有解除**：逐項看阻塞原因與預計解除時間，
   到了就自己把那一行改回`- [ ]`並繼續往下做，不需要另外請示。
2. **佇列深度檢查（門檻與目標值來自`research/queue_depth_config.py`
   單一事實來源，不在這裡硬寫數字——2026-09-20總司令裁示【Q4前視與
   #23無法重現】四要求：CLAUDE.md/這份prompt/兩份CONTINUATION_
   PROMPT.txt過去各自硬寫過這兩個數字，2026-09-19門檻從5改12時只有
   部分位置同步更新，另外兩份靜態prompt檔停留在舊版整整五輪沒被
   發現）**：`PENDING_QUEUE.md`裡**真正能動手做的`- [ ]`項目**（不含
   `- [!]`阻塞項，阻塞項不會被消化，算進門檻會失去意義）若低於
   {MIN_QUEUE_DEPTH}項，有責任自己補、一次補到{TARGET_QUEUE_DEPTH}項
   （來源優先序：①本檔「常備backlog」區塊 ②`research/REPORT.md`/
   `LEADS.md`/`STRATEGY_GRAVEYARD.md`裡寫著「待辦」「下一步」「未解決」但沒
   進佇列的項目 ③`HYPOTHESIS_QUEUE.md`排隊中的假設），補入時標「[自走補入]」
   與來源出處，不需要事先請示。

## 一定要遵守
1. 先讀 `C:\\alpha\\alpha-app\\CLAUDE.md`（尤其「零之一、停下條件改為白名單」
   「七、資料原則」「七之二、常駐服務發布紀律」「四之二、驗收證據原則」）與
   `C:\\alpha\\CLAUDE.md`（外部 API 頻率上限清單）。
2. 每一項做完都要跑 `node scripts/smoke_test.mjs`，**全過才能 commit**。
3. 動到 `research/alpha_live_server.py` 或 `research/shioaji_quotes.py` 的 commit，
   最後一步必須重啟服務並跑四步驗證（重啟→比對 build sha→OPTIONS 預檢→stale_process=false）。
4. 做完一項就把 PENDING_QUEUE 那一行從 `- [ ]` 改成 `- [x]` 並補上做了什麼、證據是什麼。
5. 更新 `PROGRESS.md`（最新的寫最上面），然後 commit + push——**收工時寫一份，
   不要每做完一項就想回報**，一輪做到不能再做為止再一次寫齊每一項的段落
   （做了什麼／證據／`[自行裁量]`的地方／BLOCKED的原因與解除條件）。
6. **每個 commit 訊息最後一行加 `DevQueue-Cycle: {cycle_id}`**（2026-09-15 總司令
   交辦：這樣他從 `dev_queue_cycle.log` 看到 cycle_id 就能直接對回是哪個 commit
   做的，不用去猜時間戳）——本輪做好幾項、好幾個 commit 的話，每個都要加這行，
   不是只加在最後一個。

## 只有下面這五種情況才停，其餘一律自行裁量繼續做
- 需要總司令親自操作（登入、實機測試、花錢、要他裁示）
- 不可逆動作（刪資料、解鎖 holdout、真實下單）
- 要修改既有已驗證關卡的通過門檻（GATE1~6、violation_rate門檻等）
- 法遵疑慮（ToS、爬蟲、付費資料、robots.txt）
- 同一項試了兩次還是失敗

**「這件事應該先請示一下」不是停下理由。** 遇到不確定但屬於可還原的技術選擇
（例如兩個做法選哪個、參數用哪個保守值、舊交辦項沒寫分支不知道怎麼繼續），
**選一個、寫下為什麼選它、繼續做**，在PENDING_QUEUE那一項補記時標`[自行裁量]`，
不要停下來問——總司令下一次讀的時候可以推翻，推翻的成本遠低於空轉一整晚。

停下時執行：
    python scripts/dev_queue_runner.py block "具體原因"
它會把那一項標成阻塞並寫進 PENDING_QUEUE，然後**換下一項繼續做，不是結束整輪**
（除非所有項目都變成BLOCKED或已無`- [ ]`項目可做）。

## 誠實要求
- 沒驗過的不要說「已完成」，寫「已實作但未驗證」。
- 查不到資料就照 CLAUDE.md 的三來源查證紀律，列出查了哪三個來源。
- 不准為了讓測試過而放寬測試。
"""
    PROMPT_OUT.write_text(prompt, encoding="utf-8", newline="\n")
    _note_dispatch(text)
    print(f"PROMPT_READY: {key}（{item_class(text)}類）")
    return 0


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "next"
    if cmd == "next":
        nxt = find_next()
        if nxt is None:
            print("NO_PENDING_ITEM")
            return 3
        print(re.sub(r"^- \[ \]\s*", "", nxt[1]).strip()[:200])
        return 0
    if cmd == "prompt":
        return build_prompt()
    if cmd == "check_collision":
        return check_collision()
    if cmd == "block":
        return mark_blocked(sys.argv[2] if len(sys.argv) > 2 else "未說明原因")
    if cmd in ("ok", "fail"):
        return record(cmd)
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
