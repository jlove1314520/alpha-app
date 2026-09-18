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

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "PENDING_QUEUE.md"
STATE = ROOT / "research" / "data" / "dev_queue_state.json"
PROMPT_OUT = ROOT / "research" / "DEV_QUEUE_PROMPT.txt"
TZ = timezone(timedelta(hours=8))
MAX_CONSECUTIVE_FAILS = 2

sys.path.insert(0, str(ROOT / "research"))
import marathon_lock  # noqa: E402 -- 同目錄下的鎖工具，重用它的鎖檔格式與陳舊門檻判斷

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


def item_class(text: str) -> str:
    """這一項是債務、產品還是研究。以 ORDER 清單的標記為準，清單沒有就當債務。"""
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
    """檔案原文（不只是「- [ ]」那幾行）裡是否還留著🔲／進行中／未開始這類散文狀態字樣。"""
    return bool(STALE_STATUS_MARKERS.search(QUEUE.read_text(encoding="utf-8")))


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


def build_prompt() -> int:
    # 2026-09-18（Cowork【重構.B收成前必修】順手修）：這道自檢要在find_next()
    # 之前跑——標記不只一組時，即使find_next()剛好因為既有防呆（垃圾對不上
    # by_key就退回檔案順序）矇對答案，權威排序清單本身仍是壞的，不能因為
    # 這次矇對就放行，必須整輪不派工、等標記修好。
    ambiguity = _order_marker_ambiguity()
    if ambiguity:
        detail = f"QUEUE_ORDER_MARKER_AMBIGUOUS: {ambiguity}"
        _record_format_mismatch(detail)
        PROMPT_OUT.write_text("NO_PENDING_ITEM", encoding="utf-8")
        print(detail)
        return 5
    nxt = find_next()
    if nxt is None:
        PROMPT_OUT.write_text("NO_PENDING_ITEM", encoding="utf-8")
        if _has_any_pending_line():
            # 還有「- [ ]」項目，只是全部是[研究]類（不歸DevQueue管）——這是
            # 正常讓路，不是矛盾。清掉舊的mismatch旗標（狀態已經自癒）。
            _clear_format_mismatch()
            print("NO_PENDING_ITEM_FOR_DEVQUEUE：剩餘待辦皆為[研究]類，留給"
                  "marathon／hypothesis_queue軌")
            return 3
        if _stale_status_markers_present():
            detail = "find_next()回None但檔案仍有🔲/進行中/未開始字樣，判定為格式不符而非真的做完"
            _record_format_mismatch(detail)
            print(f"QUEUE_FORMAT_MISMATCH: {detail}")
            return 4
        _clear_format_mismatch()
        print("NO_PENDING_ITEM")
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
2. **佇列深度檢查**：`PENDING_QUEUE.md`裡`- [ ]`加`- [!]`的未完成項若低於5項，
   有責任自己補（來源優先序：①本檔「常備backlog」區塊 ②`research/REPORT.md`/
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
