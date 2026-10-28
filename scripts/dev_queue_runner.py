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
WRAP_UP_MIN = 45  # 先.九十三-3：每輪 45 分鐘自行存檔收尾（外層 run-dev-queue-cycle.ps1 60 分鐘強制中止）
MAX_CONSECUTIVE_FAILS = 2

sys.path.insert(0, str(ROOT / "research"))
import marathon_lock  # noqa: E402 -- 同目錄下的鎖工具，重用它的鎖檔格式與陳舊門檻判斷
try:  # 先.十六-一 單發防撞；匯入失敗 fail open（寧可漏抓不可癱瘓，CLAUDE.md 十二）
    from interactive_yield import has_mark as _yield_has_mark, report as _yield_report  # noqa: E402
except Exception:  # noqa: BLE001
    def _yield_has_mark(text):  # type: ignore[misc]
        return False

    def _yield_report(lines):  # type: ignore[misc]
        return []
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
# 2026-10-07（先.四十三-二）：殘留檔判定。實測 DevQueue 停擺 15.8 小時的根因：三個殘留檔「內容」從 04:31
# 起就沒變，但其他 wrapper 每次 git pull --autostash 都會把它們收起再放回、刷新修改時間，於是每輪都像
# 「剛被改過」。改為記錄每個髒檔的內容雜湊：同一內容持續 ≥ RESIDUAL_MINUTES 分鐘、且沒有執行中程序的
# 命令列提到它 → 視為殘留，記警告後照常執行（不刪、不還原、不 commit，留給人或原寫手處理）。
RESIDUAL_MINUTES = 60
DIRTY_SEEN = ROOT / "research" / ".devqueue_dirty_seen.json"
# 2026-10-22（收件匣 013）：mark_blocked() 自己把條目改成 - [!] 後不 commit，這份未提交的改動被當成「有人在中途」，
# 加上 AlphaConnectivity 每 30 分鐘 pull --autostash 刷新修改時間，DevQueue 04:22 起連續讓路 3 小時。
# mark_blocked() 寫完記下 PENDING_QUEUE.md 的內容雜湊；檔案內容仍完全等於這個雜湊＝只有守門員自己的改動，不讓路。
# 任何人之後再改一個字，雜湊就不同，照舊讓路（不放寬真保護）。
RUNNER_WRITE = ROOT / "research" / ".devqueue_runner_write.json"
OTHER_TRACKS = ("marathon", "hypothesis_queue")  # devqueue自己的鎖由wrapper另外處理，不在這裡查
MACHINE_WRITTEN = [
    re.compile(r"^data/"),                    # 全部是排程產生的資料檔
    re.compile(r"^research/[^/]+\.log$"),     # 各 cycle 的執行日誌
    re.compile(r"^research/[^/]+\.jsonl$"),   # append-only 觀測紀錄
    re.compile(r"^research/data/[^/]+\.jsonl$"),  # 先.八十五-1：research/data/ 底下的 append-only 紀錄（例 adjustment_anomaly_warnings.jsonl 由 adjust.py 每次還原價計算寫入；10/13 23:01 因它讓路）
    re.compile(r"^research/\.[^/]+$"),        # .pid / .lock / .*_state.json 等隱藏狀態檔
    re.compile(r"^research/DEV_QUEUE_PROMPT\.txt$"),  # 本專案每輪重寫的提示檔
    re.compile(r"^research/lab/"),            # 研究室.一（先.一百）：Cowork 每週日寫入深度研究設定／說法紀錄，由研究室.六驗證後提交
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


def _file_hash(path: Path) -> str | None:
    try:
        import hashlib
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _running_cmdlines() -> list[str] | None:
    """目前所有 python／powershell／node 程序的命令列（小寫）。查詢失敗回 None（呼叫端視為「不確定」）。"""
    # 2026-10-22（收件匣 013）：排除自己這個程序與呼叫它的 wrapper——本程式（dev_queue_runner）本身就在
    # PENDING_QUEUE.md 的「可能寫手」名單裡，自己的命令列永遠命中，殘留判定對 PENDING_QUEUE.md 從來不會成立。
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python|powershell|node|pwsh' } "
             "| ForEach-Object { \"$($_.ProcessId)`t$($_.CommandLine)\" }"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        own = {str(os.getpid()), str(os.getppid())}
        out = []
        for ln in r.stdout.splitlines():
            pid, _, cmd = ln.partition("\t")
            if cmd.strip() and pid.strip() not in own:
                out.append(cmd.strip().lower())
        return out
    except Exception as e:  # noqa: BLE001 — 守門員自己失敗只降級（CLAUDE.md 十二）
        print(f"WARN: 查詢執行中程序失敗（{type(e).__name__}），殘留判定本輪保守視為仍在寫", flush=True)
        return None


def _residual_ok(path: str, now: float, seen: dict, cmdlines: list[str] | None) -> bool:
    """同一內容已持續 ≥RESIDUAL_MINUTES 且沒有程序命令列提到它（檔名主幹）→ True。會更新 seen。"""
    h = _file_hash(ROOT / path)
    rec = seen.get(path)
    if h is None:
        return False
    if not rec or rec.get("hash") != h:
        seen[path] = {"hash": h, "first_seen": now}
        return False
    if (now - float(rec.get("first_seen", now))) / 60.0 < RESIDUAL_MINUTES:
        return False
    if cmdlines is None:
        return False
    names = {Path(path).stem.lower()} | _writers_of(path)
    return not any(n in c for n in names for c in cmdlines)


def _writers_of(path: str) -> set[str]:
    """repo 裡提到這個檔名的程式（.py／.ps1／.vbs）＝可能的寫手，回傳其檔名主幹（小寫）。失敗回空集合。"""
    base = Path(path).name
    try:
        r = subprocess.run(["git", "-C", str(ROOT), "grep", "-l", "-F", base, "--", "*.py", "*.ps1", "*.vbs"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        return {Path(f).stem.lower() for f in r.stdout.splitlines() if f.strip() and Path(f).name != base}
    except Exception as e:  # noqa: BLE001
        print(f"WARN: 查寫手失敗（{type(e).__name__}）", flush=True)
        return set()


# 2026-10-21（先.一二二-13）：PENDING_QUEUE.md 是佇列本身，Cowork／其他輪次在檔尾新增條目不代表有人在中途改程式
# （10/20 20:01／20:31／21:01 三輪都因此讓路）。只有「既有行被改寫或刪除」才算非機器改動；純檔尾新增照常執行。
APPEND_TOLERANT = ("PENDING_QUEUE.md",)
_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def _is_append_only_diff(diff_text: str, old_line_count: int) -> bool:
    """git diff -U0 的輸出是否只有「接在舊檔最後一行之後的新增」。沒有任何 hunk（只改權限等）也回 False。"""
    hunks = 0
    for ln in diff_text.splitlines():
        m = _HUNK.match(ln)
        if not m:
            continue
        hunks += 1
        old_start, old_len = int(m.group(1)), int(m.group(2) or "1")
        if old_len != 0:          # 有刪除或改寫既有行
            return False
        if old_start < old_line_count:   # 新增插在中間（-U0 的純新增 hunk，old_start＝插入點前一行）
            return False
    return hunks > 0


def _append_only_change(path: str) -> bool:
    """這個檔相對 HEAD 是否只有檔尾新增。自己出錯一律回 False（照舊視為真改動、讓路），只印警告。"""
    try:
        diff = subprocess.run(["git", "-C", str(ROOT), "diff", "-U0", "--no-color", "HEAD", "--", path],
                              capture_output=True, text=True, check=True, encoding="utf-8", errors="replace",
                              timeout=60).stdout
        old = subprocess.run(["git", "-C", str(ROOT), "show", f"HEAD:{path}"],
                             capture_output=True, check=True, timeout=60).stdout
        return _is_append_only_diff(diff, old.count(b"\n") + (0 if old.endswith(b"\n") or not old else 1))
    except Exception as e:  # noqa: BLE001 — 守門員自己失敗只降級（CLAUDE.md 十二）
        print(f"WARN: 判斷 {path} 是否純檔尾新增失敗（{type(e).__name__}），照舊視為改動", flush=True)
        return False


# 2026-10-22（收件匣 016）：紀錄改成多檔 {"files": {路徑: 雜湊}}——除了 mark_blocked() 的 - [!]，
# wrapper 每輪收工也記下這輪留在工作樹、沒來得及 commit 的 PENDING_QUEUE.md／PROGRESS.md（git_op_lock 被占時）。
# 下一輪 check_collision 看到內容仍等於紀錄＝DevQueue 自己的殘留 → 不讓路、先代為 commit；有人改一個字就照舊讓路。
OWN_TRACKED = ("PENDING_QUEUE.md", "PROGRESS.md")


def _load_runner_write() -> dict:
    """回傳 {路徑: 雜湊}。舊格式 {"path","hash"} 也讀。讀不到回 {}；格式壞掉丟例外給呼叫端（照舊讓路）。"""
    try:
        rec = json.loads(RUNNER_WRITE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if "files" in rec:
        return {k: v for k, v in rec["files"].items() if v}
    return {rec["path"]: rec["hash"]} if rec.get("path") and rec.get("hash") else {}


def _only_runner_write(path: str) -> bool:
    """檔案內容是否仍等於 DevQueue 自己上次寫入／收工時記下的雜湊。自己出錯一律回 False（照舊讓路），只印警告。"""
    try:
        h = _load_runner_write().get(path)
        return bool(h) and _file_hash(ROOT / path) == h
    except Exception as e:  # noqa: BLE001 — 守門員自己失敗只降級（CLAUDE.md 十二）
        print(f"WARN: 讀守門員寫入紀錄失敗（{type(e).__name__}），照舊視為改動", flush=True)
        return False


def _record_runner_write(*paths: str) -> None:
    try:
        try:
            files = _load_runner_write()
        except Exception:  # noqa: BLE001 — 舊紀錄壞掉就重寫
            files = {}
        for path in paths:
            files[path] = _file_hash(ROOT / path)
        RUNNER_WRITE.write_text(json.dumps({"files": files, "at": datetime.now(TZ).isoformat(timespec="seconds")},
                                           ensure_ascii=False), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        print(f"WARN: 守門員寫入紀錄失敗（{type(e).__name__}），下一輪可能因自己的標記讓路", flush=True)


def _dirty_vs_head(path: str) -> bool:
    r = subprocess.run(["git", "-C", str(ROOT), "diff", "--quiet", "HEAD", "--", path], capture_output=True, timeout=60)
    return r.returncode == 1


def record_own_dirty() -> int:
    """wrapper 每輪收工呼叫：把這輪留在工作樹、還沒 commit 的 OWN_TRACKED 檔記下內容雜湊。永遠 exit 0（十二節）。"""
    try:
        dirty = [p for p in OWN_TRACKED if (ROOT / p).exists() and _dirty_vs_head(p)]
        if dirty:
            _record_runner_write(*dirty)
        print(f"RECORDED_OWN_DIRTY: {', '.join(dirty) or '（無）'}")
    except Exception as e:  # noqa: BLE001
        print(f"WARN: record_own_dirty 失敗（{type(e).__name__}），不影響本輪", flush=True)
    return 0


def _commit_own_leftovers() -> None:
    """check_collision 判定 PROCEED 之後：工作樹裡內容仍等於紀錄的 OWN_TRACKED 檔＝上一輪 DevQueue 自己的殘留，
    先代為 commit（local_git_commit.commit_paths：取 git_op_lock、只收這幾個檔、pull 套回失敗有處理）。
    自身任何失敗只印警告、不擋本輪（十二節）。"""
    try:
        own = [p for p in OWN_TRACKED if (ROOT / p).exists() and _dirty_vs_head(p) and _only_runner_write(p)]
        if not own:
            return
        import local_git_commit as LGC  # noqa: PLC0415
        res = LGC.commit_paths(own, "DevQueue 上一輪收工紀錄代為提交（收工時未能 commit，內容與當時紀錄的雜湊相同）")
        print(f"INFO: 上一輪 DevQueue 留下的 {', '.join(own)} 代為提交：{res}", flush=True)
        if res.startswith("已 commit"):
            files = _load_runner_write()
            for p in own:
                files.pop(p, None)
            RUNNER_WRITE.write_text(json.dumps({"files": files, "at": datetime.now(TZ).isoformat(timespec="seconds")},
                                               ensure_ascii=False), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        print(f"WARN: 代為提交上一輪殘留失敗（{type(e).__name__}: {e}），本輪照常執行", flush=True)


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
    try:
        seen = json.loads(DIRTY_SEEN.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        seen = {}
    dirty_now = set()
    cmdlines = "unset"
    for line in out.splitlines():
        if not line or line.startswith("??"):  # untracked 不算，跟白名單邏輯一致
            continue
        path = line[3:]  # porcelain 是「2碼狀態+1空格+路徑」
        if any(p.match(path) for p in MACHINE_WRITTEN):
            continue
        dirty_now.add(path)
        try:
            age_min = (now - (ROOT / path).stat().st_mtime) / 60.0
        except OSError:
            continue  # 檔案已被刪除等邊界情況，不當成碰撞訊號
        if age_min < COLLISION_RECENCY_MINUTES:
            if path in OWN_TRACKED and _only_runner_write(path):
                print(f"INFO: {path} 的未提交改動是 DevQueue 自己留下的（內容與紀錄的雜湊相同，"
                      f"{age_min:.1f} 分鐘前被刷新修改時間），不算有人在中途，照常執行", flush=True)
                continue
            if path in APPEND_TOLERANT and _append_only_change(path):
                print(f"INFO: {path} 只有檔尾新增條目（{age_min:.1f} 分鐘前），不算有人在中途，照常執行", flush=True)
                continue
            if cmdlines == "unset":
                cmdlines = _running_cmdlines()
            if _residual_ok(path, now, seen, cmdlines):
                print(f"WARN: {path} 內容已 ≥{RESIDUAL_MINUTES} 分鐘未變、無執行中程序提到它（修改時間 {age_min:.1f} 分鐘前"
                      f"多半是其他排程 autostash 刷新），視為殘留、照常執行；請人工確認後 commit 或還原", flush=True)
                continue
            hits.append(f"{path}（{age_min:.1f}分鐘前）")
        else:
            _residual_ok(path, now, seen, None)  # 只更新內容紀錄
    try:
        DIRTY_SEEN.write_text(json.dumps({k: v for k, v in seen.items() if k in dirty_now}, ensure_ascii=False, indent=1),
                              encoding="utf-8")
    except OSError as e:
        print(f"WARN: 殘留紀錄寫入失敗（{type(e).__name__}），不影響本輪", flush=True)
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
    _commit_own_leftovers()
    return 0

# 2026-09-18（總司令裁示【改為連續自走】）：這幾個regex對應CLAUDE.md
# 「零之一、停下條件改為白名單」七條裡機器可以事先偵測的幾條（2需總司令
# 親自操作、3解鎖holdout、4真錢下單、5改GATE門檻、6法遵疑慮）——寧可
# 誤判成「要停」也不要讓無人值守的行程去點登入、花錢、悄悄調鬆驗證門檻、
# 或做出法遵有疑慮的事。條件1（花錢/不可逆）與條件7（佇列真空）由其他
# 邏輯處理，不在這裡。
NEEDS_USER = re.compile(
    r"登入|授權|實機|親自|購買|採購|付費|花錢|信用卡|核准|裁示|截圖給|公司手機|"
    r"手動貼|貼給總司令|請總司令|等總司令|需總司令|待總司令|本人登入")
IRREVERSIBLE = re.compile(
    r"刪除|清空|holdout|真實下單|下單 API|不可逆|覆蓋.*資料庫|"
    r"調鬆.*門檻|放寬.*門檻|改.*GATE\d|修改.*通過門檻|violation_rate門檻|"
    r"ToS|robots\.txt|服務條款|繞過驗證碼|付費資料|爬蟲.*繞")

# 2026-10-11（先.六十二-1）守門員誤判修正。實測誤判：「不接付費模型」被當成要花錢、
# 「刪除舊清單的本機 localStorage 鍵」被當成不可逆、「Gateway 需登入時只顯示 CTA」被當成要總司令登入。
# 改為：①只比對「標題（第一組 **…**）＋做法句（「做法：」開頭的分句）」；條目沒寫「做法：」時，比對標題＋
# 括號外本文；〔來源：…〕〔現況：…〕〔心跳／驗收…〕這類描述性分句一律不看。②否定詞（不接／不用／不得／
# 不做／無需／非）後面 8 個字內的命中不算。③「X 時」條件句（命中後 3 字內接「時」）是描述狀態，不算要人動手。
# ④刪除／清空的對象若是 App 內可重建的東西（localStorage、快取、登記、allowlist、暫存）不算不可逆。
# 十二節：這些判斷自己出錯時一律降級回舊版（整句比對），寧可多擋一次，不可讓守門員崩潰。
GUARD_NEGATIONS = ("不接", "不用", "不得", "不做", "無需", "非")
GUARD_NEG_WINDOW = 8
_GUARD_DESC_PREFIX = ("來源：", "現況：", "心跳：", "驗收：", "心跳位置：", "驗收條件：")
_GUARD_SAFE_DELETE = re.compile(r"localStorage|快取|cache|登記|allowlist|暫存|本機.{0,6}鍵")
# 2026-10-28 收件匣 028：「總司令裁示已核准」「核准後」「裁示：甲」「（收件匣 027）」這類＝已經裁示過、交辦執行，
# 不是要人動手。命中字前 6 字內有「已」、後面緊接「已核准／已同意／已定案／已裁示」「後」「：」、或前後 12 字內有
# 「收件匣 NNN」→ 不算（只對需總司令那組，不可逆那組照舊）。真的要人操作的寫法照擋：命中字本身是
# 請／等／需／待總司令、本人登入、貼給總司令，或前後 6 字內出現這些字。10/23 先.一三二-0、10/28 先.一三八-1 都是被這個誤擋空轉。
GUARD_APPROVED_ON = True  # 自測用開關（selftest_dev_queue_guard_approved.py 比對修前／修後），正式一律 True
GUARD_APPROVED_WINDOW = 6
_GUARD_STILL_NEEDS = re.compile(r"請總司令|等總司令|需總司令|待總司令|貼給總司令|本人")
_GUARD_APPROVED_POST = re.compile(r"^(已(核准|同意|定案|裁示)|後|[：:])")
_GUARD_INBOX_REF = re.compile(r"收件匣\s*\d{3}")


def guard_scope(clean: str) -> str:
    """回傳守門員要比對的文字：標題＋做法句；沒有做法句時用標題＋括號外本文。"""
    m = re.search(r"\*\*(.+?)\*\*", clean)
    title = m.group(1) if m else ""
    segs = re.split(r"[；;〔〕]", clean)
    how = [s for s in segs if s.strip().startswith("做法：")]
    if how:
        return title + "\n" + "\n".join(how)
    body = re.sub(r"〔[^〕]*〕", " ", clean)
    if m:
        body = body.replace(m.group(0), " ")
    body_segs = [s for s in re.split(r"[；;]", body) if not s.strip().startswith(_GUARD_DESC_PREFIX)]
    return title + "\n" + "；".join(body_segs)


def _guard_hit_ignored(text: str, mt: "re.Match", irreversible: bool) -> bool:
    p = mt.start()
    pre = text[max(0, p - GUARD_NEG_WINDOW - 2):p]
    for neg in GUARD_NEGATIONS:
        i = pre.rfind(neg)
        if i >= 0 and (len(pre) - (i + len(neg))) <= GUARD_NEG_WINDOW:
            return True
    if not irreversible and "時" in text[mt.end():mt.end() + 3]:
        return True
    if not irreversible and GUARD_APPROVED_ON and _guard_already_approved(text, mt):
        return True
    if irreversible and mt.group(0) in ("刪除", "清空"):
        clause = re.split(r"[，。；;、\n]", text[mt.end():])[0][:30]
        if _GUARD_SAFE_DELETE.search(clause):
            return True
    return False


def _guard_already_approved(text: str, mt: "re.Match") -> bool:
    """收件匣 028：命中的「核准／裁示…」是在講已經裁示過的事（見 _GUARD_APPROVED_POST 上方註解）。"""
    w = GUARD_APPROVED_WINDOW
    p, e = mt.start(), mt.end()
    pre, post = text[max(0, p - w):p], text[e:e + w]
    if _GUARD_STILL_NEEDS.search(pre + mt.group(0) + post):
        return False
    return ("已" in pre or bool(_GUARD_APPROVED_POST.match(post))
            or bool(_GUARD_INBOX_REF.search(text[max(0, p - 12):e + 12])))


def guard_hits(clean: str) -> dict:
    """{'needs_user': [命中字…], 'irreversible': [命中字…]}；空清單＝不擋。自身出錯→退回整句比對（fail safe：寧可多擋）。"""
    out = {"needs_user": [], "irreversible": []}
    try:
        scope = guard_scope(clean)
        for key, rx, irr in (("needs_user", NEEDS_USER, False), ("irreversible", IRREVERSIBLE, True)):
            out[key] = [mt.group(0) for mt in rx.finditer(scope) if not _guard_hit_ignored(scope, mt, irr)]
    except Exception as e:  # noqa: BLE001
        _safe_print(f"WARN_DETECTOR_CRASHED: guard_hits failed ({type(e).__name__})，退回整句比對")
        out = {"needs_user": [m.group(0) for m in NEEDS_USER.finditer(clean)],
               "irreversible": [m.group(0) for m in IRREVERSIBLE.finditer(clean)]}
    return out


def guard_precheck() -> list:
    """先.六十二-3：每輪開始時對所有 - [ ] 預跑兩組偵測，只印「會被擋」清單；不改任何標記。自身失敗只印警告。"""
    found = []
    try:
        for ln in _lines():
            if not ln.lstrip().startswith("- [ ]"):
                continue
            clean = re.sub(r"^\s*- \[ \]\s*", "", ln).strip()
            h = guard_hits(clean)
            if h["needs_user"] or h["irreversible"]:
                found.append((clean[:60], h))
        for title, h in found:
            _safe_print(f"GUARD_PRECHECK_WARN：{title}… 會被擋（需總司令：{'、'.join(h['needs_user']) or '—'}；"
                        f"不可逆：{'、'.join(h['irreversible']) or '—'}）。只警告、不改標記，由互動視窗處理")
        if not found:
            _safe_print("GUARD_PRECHECK：所有 - [ ] 項目都不會被守門員擋下")
    except Exception as e:  # noqa: BLE001
        _safe_print(f"WARN_DETECTOR_CRASHED: guard_precheck failed ({type(e).__name__})，本輪略過自檢")
    return found


# 先.八十五-1c：佇列 ≥12 項中至少 6 項要 DevQueue 可執行（非互動視窗、不被守門員擋；先.一二七-A 起[研究]也算）
DEVQUEUE_ELIGIBLE_MIN = 6

# 先.一二七-A（2026-10-21 總司令核准，收件匣 005）：AlphaMarathon／AlphaHypothesisQueue 停用，
# 研究軌併入 DevQueue——[研究]類也取件，一輪只戴一頂帽子（提示詞依類別帶研究紀律）。
# 還原舊行為（DevQueue 跳過[研究]）：改成 False，並把兩個排程 Enable 回來。
RESEARCH_MERGED_INTO_DEVQUEUE = True


def _skip_classes() -> tuple:
    """DevQueue 不取件的類別。互動視窗專屬（含碰核心研究檔案的條目）永遠跳過。"""
    return ("互動視窗",) if RESEARCH_MERGED_INTO_DEVQUEUE else ("研究", "互動視窗")


def eligible_precheck() -> int:
    """印 DEVQUEUE_ELIGIBLE 計數；不足 DEVQUEUE_ELIGIBLE_MIN 印 _LOW 警告。只印、不改標記；自身失敗只降級。"""
    try:
        n = 0
        for _i, ln in _pending_lines(_lines()):
            if item_class(ln) in _skip_classes():
                continue
            h = guard_hits(re.sub(r"^\s*- \[ \]\s*", "", ln).strip())
            if not (h["needs_user"] or h["irreversible"]):
                n += 1
        tag = "DEVQUEUE_ELIGIBLE_LOW" if n < DEVQUEUE_ELIGIBLE_MIN else "DEVQUEUE_ELIGIBLE"
        _safe_print(f"{tag}：DevQueue 可執行的 - [ ] 共 {n} 項（下限 {DEVQUEUE_ELIGIBLE_MIN}，先.八十五-1c）")
        return n
    except Exception as e:  # noqa: BLE001
        _safe_print(f"WARN_DETECTOR_CRASHED: eligible_precheck failed ({type(e).__name__})，本輪略過")
        return -1


# 先.六十七-5：條目寫著總司令已裁示解凍／核准，卻仍標 [!] → 標記與裁示不一致（例：-6 先.六十五 已解凍仍標 [!]）。
# 排除「待／需／經／須／等／請 總司令核准」與「核准後／前」這類解除條件寫法，只抓已發生的裁示。
APPROVAL_STALE_PAT = re.compile(r"(?<![待需經須等請])總司令(?:已|於[^。；，]{0,12})?(?:裁示)?(?:解凍|核准|同意)(?![後前？?])"
                                r"|裁示解凍|總司令貼上即(?:同意|生效)")


def approval_precheck() -> list:
    """先.六十七-5：每輪預檢列出「含總司令裁示解凍／核准字樣但仍標 [!]」的條目；只印警告、不改標記，由互動視窗處理。
    ``` 裁示引文內的行不看。自身失敗只印警告。"""
    found = []
    try:
        lines = _lines()
        fenced = _fenced_line_indices(lines)
        for i, ln in enumerate(lines):
            if i in fenced or not ln.startswith("- [!]"):
                continue
            m = APPROVAL_STALE_PAT.search(ln)
            if m:
                found.append((item_key(ln)[:40], ln[max(0, m.start() - 6):m.end() + 6]))
        for key, ctx in found:
            _safe_print(f"APPROVAL_PRECHECK_WARN：{key} 仍標 [!]，但條目內有「{ctx}」。只警告、不改標記，由互動視窗開工時處理")
    except Exception as e:  # noqa: BLE001
        _safe_print(f"WARN_DETECTOR_CRASHED: approval_precheck failed ({type(e).__name__})，本輪略過自檢")
    return found


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


def _fenced_line_indices(lines: list[str]) -> set[int]:
    """回傳落在 ``` 程式碼區塊內的行號集合。

    2026-10-11（DevQueue 20261011-010102 發現）：三之二節要求裁示原文先抄進
    PENDING_QUEUE，原文常放在 ``` 區塊裡且本身含「- [ ] 常備.開發-11…」這種行；
    舊版只看行首，把引文當待辦，已完成的 -11～-22 會被一項項重派。引文不是待辦。
    自身失敗（第十二節）→ 回空集合，退回舊行為（寧可重派，不可癱瘓）。"""
    try:
        out, inside = set(), False
        for i, ln in enumerate(lines):
            if ln.lstrip().startswith("```"):
                inside = not inside
                continue
            if inside:
                out.add(i)
        return out
    except Exception as e:  # noqa: BLE001
        _safe_print(f"⚠️ _fenced_line_indices 失敗，退回不排除引文：{e}")
        return set()


def _pending_lines(lines: list[str]) -> list[tuple[int, str]]:
    """真正的待辦：`- [ ]` 開頭且不在 ``` 引文區塊內。"""
    fenced = _fenced_line_indices(lines)
    return [(i, ln) for i, ln in enumerate(lines) if ln.startswith("- [ ]") and i not in fenced]


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


def _find_next_base(skip: frozenset = frozenset()) -> tuple[int, str] | None:
    """回傳 (行號, 該行文字)，找不到回 None。只認 `- [ ]` 開頭、跳過 `- [!]`。

    優先依頂端的權威順序清單取件；清單裡的項目都做完（或都被標成阻塞）之後，
    再回到檔案順序處理剩下的。**`[研究]` 類項目一律跳過**（2026-09-18新增，
    見下方迴圈內註解）——這支只服務 DevQueue（開發帽），研究類工作交給
    marathon／hypothesis_queue 讀同一份檔案自己接手。**標「（互動視窗執行」
    的項目一律跳過**（2026-09-30新增，見`item_class()`docstring）——這類
    項目通常涉及CLAUDE.md「十三、核心研究檔案單一寫入者」保護的檔案
    （`research/adjust.py`等），只能由跟總司令即時對話的互動視窗session
    修改，DevQueue不得代做。回 None 不代表沒有任何待辦，只代表「沒有輪到
    DevQueue 做的」，呼叫端要用 `_has_any_pending_line()` 分辨這兩種情況。
    """
    lines = _lines()
    # 2026-10-05（先.十六-一）：帶「〔互動視窗執行中〕」標記的條目在 cycle log 記「讓行」
    # （實際跳過由 item_class()==「互動視窗」達成）；偵測自身失敗只降級
    try:
        for _m in _yield_report(lines):
            _safe_print(_m)
    except Exception:  # noqa: BLE001
        pass
    pending = _pending_lines(lines)
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
            # 先.一二七-A（2026-10-21）：研究軌併入 DevQueue 後不再跳過，由提示詞切換研究帽。
            if cls == "研究" and not RESEARCH_MERGED_INTO_DEVQUEUE:
                continue
            if key in skip:
                continue
            if key in by_key:
                # 2026-09-30：ORDER清單條目本身只認[研究]/[產品]，不認得項目行
                # 自己標的「（互動視窗執行」中文括號註記——保險起見這裡也用
                # item_class()複查一次實際行文字，避免ORDER清單把互動視窗專屬
                # 項目標成[產品]/[債務]而繞過下面fallback分支的過濾。
                if item_class(by_key[key][1]) == "互動視窗":
                    continue
                return by_key[key]
    # 走到這裡代表：沒有ORDER清單、或清單裡沒有一項能在pending裡對上——
    # 兩種情況都退回檔案順序，但一樣要濾掉[研究]類與互動視窗專屬項目
    # （用item_class()判斷，邏輯與上面ordered分支一致，只是這裡沒有現成的
    # cls可用；互動視窗專屬見item_class() 2026-09-30新增的偵測）。
    devqueue_eligible = [(i, ln) for i, ln in pending
                         if item_class(ln) not in _skip_classes() and item_key(ln) not in skip]
    return devqueue_eligible[0] if devqueue_eligible else None


# 先.一二二-6（2026-10-20）：分批／續跑類條目做完一批仍維持 - [ ]，永遠排在檔案前面，
# 把排在後面的條目餓死（10/20 09:00～19:00 大多數輪次都在跑 V1 價格補抓）。
BATCH_ITEM_TAG = re.compile(r"\[分批\]|續跑|斷點|分批|每批|第\s*\d+\s*批")


def is_batch_item(text: str) -> bool:
    return bool(BATCH_ITEM_TAG.search(text))


def find_next() -> tuple[int, str] | None:
    """find_next 的輪替外殼：上一輪派的是分批項，這一輪若又輪到分批項就改拿下一個
    非分批的可執行條目；沒有其他可執行條目才回頭做分批工作。
    輪替邏輯自身失敗只降級（CLAUDE.md 十二節）：回傳未輪替的原結果。"""
    nxt = _find_next_base()
    try:
        if nxt is None or not is_batch_item(nxt[1]):
            return nxt
        if not _load_state().get("_last_was_batch"):
            return nxt
        skip = {item_key(nxt[1])}
        cand = nxt
        while cand is not None and is_batch_item(cand[1]):
            skip.add(item_key(cand[1]))
            cand = _find_next_base(frozenset(skip))
        if cand is not None:
            _safe_print(f"輪替：跳過分批項 {item_key(nxt[1])}，改做 {item_key(cand[1])}")
            return cand
    except Exception as e:  # noqa: BLE001
        _safe_print(f"WARN_DETECTOR_CRASHED: batch rotation failed ({type(e).__name__})")
    return nxt


def _entry_key_class(entry: str) -> tuple[str, str]:
    """把 ORDER-BEGIN 清單裡一行拆成 (項目編號key, 類別)。類別看 [產品]/[研究] 標記，都沒有就是債務。"""
    if "[研究]" in entry:
        return entry.replace("[研究]", "").strip(), "研究"
    if "[產品]" in entry:
        return entry.replace("[產品]", "").strip(), "產品"
    return entry.strip(), "債務"


INLINE_CLASS_TAG = re.compile(r"\*\*[^*]+\*\*\s*(\[研究\]|\[產品\])")
# 2026-10-13（cycle 20261013-103102）：標題內含「*」（如 scores*_list、Alpha*）時 [^*]+ 對不上，
# 先.八十一-18／-27 被誤判成債務派給 DevQueue；改成非貪婪 .+? 允許標題內出現單一星號
INLINE_INTERACTIVE_TAG = re.compile(r"\*\*.+?\*\*\s*（互動視窗(?!或)")


def item_class(text: str) -> str:
    """這一項是債務、產品、研究，還是互動視窗專屬。

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

    2026-09-30（DevQueue cycle 20260930-011601 發現並修復同一形狀的第二個
    漏洞）：`修.八`／`評.B-2`／`價值成長榜恢復`／`先.一`這類項目行用的是
    `**代號**（互動視窗執行；動 ...)`這種中文括號註記，不是`[研究]`/[產品]
    方括號標記，`INLINE_CLASS_TAG`比對不到，且這些項目多半也不在ORDER清單
    裡（是總司令當天新裁示，尚未登記進ORDER-BEGIN），於是兩層都落空、預設
    「債務」，讓`find_next()`把CLAUDE.md「十三、核心研究檔案單一寫入者」
    明定只能由互動視窗修改的項目（例如`修.八`動`research/adjust.py`）派給
    了DevQueue——跟上面「十二」節那次是同一種形狀（守門員的判準前提，隨
    佇列新增的新寫法而不再成立）。修法：新增`INLINE_INTERACTIVE_TAG`偵測
    這個中文括號寫法，回傳新類別「互動視窗」，由`find_next()`比照「研究」
    類跳過，讓真正該接手的互動視窗session去讀。

    2026-09-30（DevQueue cycle 20260930-230102 發現並修復同一形狀的第三個
    漏洞）：上面9/30當天才修好的`INLINE_INTERACTIVE_TAG`寫死要求後面緊接
    「執行」兩字，但同一天稍晚新增的`先.四-一`用的是`**先.四-一 ...**
    （互動視窗；心跳...)`——冒號改成分號、且沒有「執行」二字，`先.二-一`／
    `先.二-三`則用「（互動視窗完成 2026-09-30」。三個變體只有「（互動視窗」
    這四個字是共同前綴，「執行」只是眾多可能後綴之一。修法：把規則放寬成
    只要求「（互動視窗」前綴本身，不管後面接什麼字，但加一個否定後顧
    `(?!或)`排除掉散文裡「（互動視窗或DevQueue皆可，非單一寫入者限定檔案）」
    這種明確標示雙方都可接手的措辭（目前這類措辭都不是緊跟在`**代號**`
    之後，不會誤觸，這裡只是防未來真的有人這樣寫）。"""
    # 2026-10-05（先.十六-一）：「〔互動視窗執行中 ...〕」單發防撞標記優先於一切分類
    try:
        if _yield_has_mark(text):
            return "互動視窗"
    except Exception:  # noqa: BLE001 -- 守門員自身失敗只降級，fail open
        pass
    m = INLINE_CLASS_TAG.search(text)
    if m:
        return "研究" if m.group(1) == "[研究]" else "產品"
    if INLINE_INTERACTIVE_TAG.search(text):
        return "互動視窗"
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
    st["_last_was_batch"] = is_batch_item(text)
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
    _record_runner_write("PENDING_QUEUE.md")
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
    return bool(_pending_lines(_lines()))


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


CORE_RESEARCH_FILES = ("research/backtest/", "research/validation/", "research/adjust.py",
                       "research/pit.py", "research/trial_registry.py")


def dev_hat_block(crunch: bool) -> str:
    tail = "" if crunch else ("\n連續做下一項時**只接非[研究]類**；權威清單下一項是[研究]類就收工，"
                               "留給下一輪戴研究帽（一輪只戴一頂帽子）。")
    return ("## 本輪帽子：開發／維運（CLAUDE.md 九，先.一二七-A）\n"
            "開工先寫一句「本輪戴開發帽」（或維運帽）；必交產物照九節（開發→冒煙結果、維運→data/STATUS.json）。" + tail)


def research_hat_block(crunch: bool) -> str:
    tail = "" if crunch else ("\n連續做下一項時**只接[研究]類**；下一項不是[研究]類就收工，留給下一輪換帽。")
    core = "、".join(f"`{p}`" for p in CORE_RESEARCH_FILES)
    return f"""## 本輪帽子：研究／驗證（CLAUDE.md 九、七之三、十三；先.一二七-A 研究軌併入 DevQueue）
開工先寫一句「本輪戴研究帽」或「本輪戴驗證帽」，**擇一**：研究帽產物＝SPEC／PREREG／因子程式碼；
驗證帽產物＝`TRIALS_LEDGER` 判定。**做與判分離：同一輪不得既開發策略又宣告它有效。**{tail}
研究紀律（照舊，無例外）：
1. **事前登記**：任何回測／單發前，PREREG 先定稿 commit，再用 `research/trial_registry.py` 的
   `register_trial()` 登記（未登記的判定一律無效），之後重跑 `research/selection_bias_ledger.py` 更新 N；
   自由參數 >5 個照第 11 關計 N。只跑一次，不得看完結果回去調參重測。
2. **試驗帳本單一寫入者**：`TRIALS_REGISTRY.jsonl`／`TRIALS_LEDGER.md` 只能經 `register_trial()` 寫，不准手改。
   描述性研究不登記試驗時，照條目指示 append `research/PROGRESS_HEARTBEAT.jsonl` 當心跳。
3. **核心研究檔案只能互動視窗改**（十三節）：{core} 可以讀、可以呼叫，**不准改原始碼**。
   需要改就把提案（發現什麼／建議怎麼改／影響哪些判定）寫進 PENDING_QUEUE 新條目並標「（互動視窗執行）」，
   這一項需要那個修改才能繼續的話，用 `block` 標阻塞，換下一項。
4. holdout（2025+）不得解鎖；天條一 MDD>50% 直接 `VIOLATES_SURVIVAL`；第 8 關用 `evaluate_gate8()`；
   含放空腿的數字附資料缺陷但書；美股結論附存活者偏誤但書。
5. FAIL／不可行一律附至少 3 個變形方向（七之三「失敗必附變形方向」），寫進 `STRATEGY_GRAVEYARD.md`。
6. 研究帽不改 `index.html`；冒煙測試照樣要跑（全過才 commit）。"""


# 2026-10-27 先.一三五-1（Cowork 收件匣 024）：DevQueue 10/24 07:28 起每輪 QUEUE_EMPTY 空轉約 70 小時——剩下的都在等 Cowork 審，
# 而 Cowork 只在總司令說「讀」時才審。兩個補救，都只在「沒有可執行的 - [ ]」時才啟動：
# (a) 24 小時預設放行：AWAITING 等 Cowork 審的草稿／提案超過 24 小時沒裁示 → 照草稿自己標的「建議選項」執行，標 [預設放行]，
#     Cowork 事後可推翻（照 PREREG 修訂規則處理）。不適用（仍要等）：解鎖或擴大 holdout、真錢、刪除／不可逆、需要密碼或本人登入、
#     新增付費資料、改既有關卡門檻（下面 DEFAULT_RELEASE_EXCLUDE 關鍵字；寧可多擋）。
# (b) QUEUE_EMPTY／GATED 連續 2 輪 → 這一輪做「候選補件」（只限台股個股層級、優先前向版，照 先.一三二-1 格式），不准空轉超過 1 小時。
AWAIT_FILE = ROOT / "research" / "AWAITING_REVIEW.md"
DEFAULT_RELEASE_HOURS = 24
DEFAULT_RELEASE_EXCLUDE = re.compile(
    r"holdout|保留資料|真錢|實盤|下單|刪除|清除|drop|不可逆|密碼|登入|本人|親手|請總司令|付費|採購|門檻|GATE\d|非阻塞")
_AWAIT_TIME = re.compile(r"(20\d\d-\d\d-\d\d) (\d\d):(\d|x)(\d|x)")


def _default_release_candidates(now: datetime | None = None, text: str | None = None) -> list[tuple[str, float]]:
    """AWAITING「等待中」表格裡等超過 24 小時、且不碰排除類別的列 → [(項目欄, 已等小時)]。自身失敗回 []（十二節）。"""
    try:
        now = now or datetime.now(TZ)
        text = AWAIT_FILE.read_text(encoding="utf-8") if text is None else text
        sec = text.split("## 等待中", 1)[1].split("\n## ", 1)[0]
        out = []
        for ln in sec.splitlines():
            if not ln.startswith("| ") or ln.startswith("| 項目") or ln.startswith("|---"):
                continue
            cells = [c.strip() for c in ln.strip("|").split("|")]
            m = _AWAIT_TIME.search(cells[1] if len(cells) > 1 else "")
            if not m:
                continue
            mm = (m.group(3) if m.group(3) != "x" else "0") + (m.group(4) if m.group(4) != "x" else "0")
            t = datetime.strptime(f"{m.group(1)} {m.group(2)}:{mm}", "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
            age = (now - t).total_seconds() / 3600
            if age >= DEFAULT_RELEASE_HOURS and not DEFAULT_RELEASE_EXCLUDE.search(ln):
                out.append((cells[0], round(age, 1)))
        return out
    except Exception as e:  # noqa: BLE001
        _safe_print(f"WARN_DETECTOR_CRASHED: default_release_candidates failed ({type(e).__name__})")
        return []


def _consecutive_idle_rounds(log_text: str | None = None) -> int:
    """dev_queue_cycle.log 最近連續幾輪是 QUEUE_EMPTY／GATED（YIELD 讓路的輪不算、也不打斷）。自身失敗回 0。
    收件匣 026 起讓路／閘門／鎖被占也寫 cycle end（YIELD／CRUNCH_GATE／USAGE_GATE／LOCK_BUSY），同樣不算、不打斷。"""
    try:
        text = (ROOT / "research" / "dev_queue_cycle.log").read_text(encoding="utf-8", errors="replace") if log_text is None else log_text
        reasons = re.findall(r"DevQueue cycle end: \S+ \S+ cycle_id=\S+ reason=(\S+)", text)
        n = 0
        for r in reversed(reasons):
            if r in ("QUEUE_EMPTY", "GATED"):
                n += 1
            elif r in ("YIELD", "CRUNCH_GATE", "USAGE_GATE", "LOCK_BUSY"):
                continue
            else:
                break
        return n
    except Exception as e:  # noqa: BLE001
        _safe_print(f"WARN_DETECTOR_CRASHED: consecutive_idle_rounds failed ({type(e).__name__})")
        return 0


def _idle_fallback_prompt() -> bool:
    """沒有可執行項目時：先試 24 小時預設放行，再試連續 2 輪空轉的候選補件。寫了提示詞回 True（本輪照常跑），否則 False。"""
    try:
        # 防重複（趕工迴圈會連續呼叫 build_prompt）：同一項 24 小時內只試一次預設放行；候選補件每小時最多一次。
        st = _load_state()
        tried = st.get("_default_release_tried", {})
        now_ts = time.time()
        cands = [c for c in _default_release_candidates() if now_ts - float(tried.get(c[0], 0)) >= DEFAULT_RELEASE_HOURS * 3600]
        if cands:
            item, age = cands[0]
            tried[item] = now_ts
            st["_default_release_tried"] = {k: v for k, v in tried.items() if now_ts - float(v) < 7 * 86400}
            _save_state(st)
            PROMPT_OUT.write_text(f"""# DevQueue 本輪：24 小時預設放行（先.一三五-1，Cowork 收件匣 024）

`research/AWAITING_REVIEW.md` 等待中的「{item}」已等 {age} 小時、沒有 Cowork 裁示，而且不屬於排除類別。
照 `C:\\alpha\\alpha-app\\CLAUDE.md`「零之二、24 小時預設放行」執行：
1. 讀 PENDING_QUEUE.md 對應條目與草稿／提案原文，找出**作者自己標的建議選項**（「建議」「推薦」「甲（建議）」之類）。
   **找不到明確的建議選項就不要自己挑**：`python scripts/dev_queue_runner.py block "預設放行：草稿沒有標建議選項"`，收工。
2. 再檢查一次：執行內容若涉及解鎖或擴大 holdout、真錢、刪除／不可逆、密碼或本人登入、新增付費資料、改既有關卡門檻 → 不做，同上 block。
3. 照建議選項執行（PREREG 定稿＋register_trial、程式、文件……照該條目原本的流程），研究紀律照舊（不碰 holdout、照實計 N）。
4. 條目與 PROGRESS 都標 **[預設放行]**，寫明「Cowork 可推翻，推翻時照 PREREG 修訂規則處理」；AWAITING 該列移到「已結案審閱紀錄」並註明 [預設放行]。
5. 冒煙全過再 commit。
""", encoding="utf-8", newline="\n")
            _safe_print(f"DEFAULT_RELEASE：{item}（已等 {age} 小時）")
            return True
        idle = _consecutive_idle_rounds()
        if idle >= 2 and now_ts - float(st.get("_last_replenish", 0)) >= 3600:
            st["_last_replenish"] = now_ts
            _save_state(st)
            PROMPT_OUT.write_text(f"""# DevQueue 本輪：候選補件（先.一三五-1，Cowork 收件匣 024；已連續 {idle} 輪 QUEUE_EMPTY／GATED）

佇列沒有可執行項目，不准再空轉。照 先.一三二-1 的格式補件：
- **只限台股個股層級**（不要 ETF、不要高股息），**優先前向版**（與模擬 J／K／L 同框架、2027-01-04 起跑，參數 ≤5）；
- 每條寫成 PENDING_QUEUE `- [ ]` 新條目（標「DevQueue 可執行」、附心跳位置與來源：墓園變形方向／LEADS／資料缺口等），至少 3 條；
- 需要 Cowork 審的草稿送 AWAITING（24 小時後適用預設放行）；
- 不碰 holdout、不算任何報酬、不登記試驗（登記等定稿）。
- **前向模擬上限＝14（現有）＝滿**（CLAUDE.md 零之二⑤，收件匣 025／027：任何一支判定或終止前不新增登記）：先看 `research/FORWARD_CANDIDATES.md` 頂端「進行中」計數；
  **上限已滿時只把候選寫進該檔候選表（機制、來源、資料、參數草案），不寫可登記的 PREREG 草稿、不送 AWAITING**，
  這一輪改補其他類（資料缺口、維運、既有模擬的追蹤程式／自測）。
冒煙全過再 commit。
""", encoding="utf-8", newline="\n")
            _safe_print(f"IDLE_REPLENISH：連續 {idle} 輪空轉 → 候選補件")
            return True
    except Exception as e:  # noqa: BLE001 — 十二節：只降級
        _safe_print(f"WARN_DETECTOR_CRASHED: idle_fallback failed ({type(e).__name__})")
    return False


def build_prompt() -> int:
    # 2026-09-19（總司令裁示【最優先·三個都是總司令自己造成的故障】一.2）：
    # 這整段矛盾偵測（含2026-09-18加的ORDER-BEGIN檢查）包一層try/except——
    # 新硬規則「任何偵測器/守門員自身失敗只能降級成一行警告，絕不得讓被
    # 監控的流程非零退出或中斷」（見CLAUDE.md對應章節）。這裡"crash"指的是
    # 偵測邏輯本身丟出未預期例外（例如未來又有別的編碼/正規表達式/檔案IO
    # 問題），不是「偵測到真的矛盾」這種設計內的return 4/5——那些是正常
    # 工作結果，不是本規則要防的對象。偵測失敗一律fail open（當成沒偵測到
    # 問題），因為「這輪漏抓一次矛盾」永遠比「DevQueue整支崩潰3小時」代價低。
    guard_precheck()  # 先.六十二-3：只印警告，自身失敗已在函式內降級
    approval_precheck()  # 先.六十七-5：同上，只印警告
    eligible_precheck()  # 先.八十五-1c：同上，只印計數／警告
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
            # 還有「- [ ]」項目，只是全部是[研究]類或「（互動視窗執行」類
            # （不歸DevQueue管）——這是正常讓路，不是矛盾。清掉舊的mismatch
            # 旗標（狀態已經自癒）。
            _clear_format_mismatch()
            _safe_print("NO_PENDING_ITEM_FOR_DEVQUEUE：剩餘待辦皆為「（互動視窗執行」類"
                         + ("" if RESEARCH_MERGED_INTO_DEVQUEUE else "或[研究]類（留給marathon／hypothesis_queue軌）")
                         + "，留給互動視窗session")
            return 0 if _idle_fallback_prompt() else 3
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
        # 2026-10-08（先.五十三-B5）：沒有 - [ ] 但還有 - [!]（時間閘／BLOCKED）→ 正常無為 GATED（exit 6），
        # 讓心跳記 last_reason=GATED，不被當成「3 小時沒有執行」的停擺。
        try:
            gated = any(ln.lstrip().startswith("- [!]") for ln in _lines())
        except Exception as e:  # noqa: BLE001
            gated = False
            _safe_print(f"WARN_DETECTOR_CRASHED: gated check failed ({type(e).__name__})")
        if gated:
            _safe_print("NO_PENDING_ITEM_GATED：剩餘項目皆為時間閘或 BLOCKED，正常無為")
            return 0 if _idle_fallback_prompt() else 6
        _safe_print("NO_PENDING_ITEM")
        return 0 if _idle_fallback_prompt() else 3
    _clear_format_mismatch()
    _, text = nxt
    key = item_key(text)
    clean = re.sub(r"^- \[ \]\s*", "", text).strip()

    # 停下條件 1、2 在產生提示詞之前就先判斷——不要讓無人值守的行程「開始做了才發現不能做」
    # 先.六十二-1：只看標題＋做法句、排除否定詞與條件句（guard_hits）
    _gh = guard_hits(clean)
    if _gh["needs_user"]:
        mark_blocked("需要總司令親自操作（登入／實機／花錢／核准），自走行程不做這類事")
        print("BLOCKED_NEEDS_USER")
        return 2
    if _gh["irreversible"]:
        mark_blocked("涉及不可逆動作，依 CLAUDE.md 必須先問過總司令")
        print("BLOCKED_IRREVERSIBLE")
        return 2

    st = _load_state()
    fails = st.get(key, {}).get("fails", 0)
    prev = f"\n注意：這一項已經連續失敗 {fails} 次。再失敗一次就會被標成阻塞交給總司令，" \
           f"所以這一輪先把「為什麼失敗」查清楚再動手。\n" if fails else ""
    cycle_id = os.environ.get("ALPHA_CYCLE_ID", "unknown")
    # 先.六十四：趕工模式（scripts/dev_queue_crunch.py 迴圈）——每次 claude -p 只做這一項，做完由迴圈立刻派下一項，
    # 這樣每一項才能各自結算（完成推播／心跳／連敗兩次標 [!]）。非趕工時維持原本「一輪做多項」的提示詞。
    crunch = os.environ.get("ALPHA_DEVQUEUE_CRUNCH") == "1"
    if crunch:
        multi = ("**趕工模式（先.六十四）：這一次只做上面這一項。** 做完、冒煙全綠、commit＋push、把那一行改成 `- [x]`、"
                 "照條目指示 append PROGRESS_HEARTBEAT 之後就**結束**——趕工迴圈會立刻派下一項給新的工作階段，"
                 "不要自己接著做下一項（否則迴圈無法逐項結算）。")
        progress_rule = ("5. 趕工模式：`PROGRESS.md` 由趕工迴圈在收工時統一寫一段（完成清單／BLOCKED／剩餘項數），"
                         "這一項**不用**寫 PROGRESS.md；條目要求的 `research/PROGRESS_HEARTBEAT.jsonl` 心跳照寫。")
        block_rule = "它會把這一項標成阻塞並寫進 PENDING_QUEUE，然後**結束這一次**——趕工迴圈會自動派下一項。"
    else:
        multi = ("做完這一項就接著做權威清單裡的下一項，**一輪之內連續做多項，做到不能再做為止**\n"
                 "（額度節流／所有項目都BLOCKED／碰到下面的停下條件才結束這一輪），不是做完一項\n"
                 "就結束。**一次做一項，每一項各自commit**，不要把好幾項混在同一個 commit 裡。")
        progress_rule = ("5. 更新 `PROGRESS.md`（最新的寫最上面），然後 commit + push——**收工時寫一份，\n"
                         "   不要每做完一項就想回報**，一輪做到不能再做為止再一次寫齊每一項的段落\n"
                         "   （做了什麼／證據／`[自行裁量]`的地方／BLOCKED的原因與解除條件）。")
        block_rule = ("它會把那一項標成阻塞並寫進 PENDING_QUEUE，然後**換下一項繼續做，不是結束整輪**\n"
                      "（除非所有項目都變成BLOCKED或已無`- [ ]`項目可做）。")

    # 先.九十三-3（2026-10-14 總司令裁示）：wrapper 60 分鐘會強制砍掉（10/14 03:01、06:31 兩輪 TIMEOUT），
    # 長時間抓取（SIC、Tiingo 等）一律在開工後 45 分鐘自行存檔收尾，下一輪續跑。
    # 先.一二一-3：最近 7 天撞過 Claude 用量上限 → 補件只排 ①資料錯 ②畫面問題 ③研究，暫停 ④文書核對。
    # 讀狀態檔失敗只降級成「沒撞過」（十二節：守門員自己壞掉不得擋主流程）。
    usage_note = ""
    try:
        _ust = json.loads((ROOT / "research" / ".claude_usage_state.json").read_text(encoding="utf-8"))
        _hit = _ust.get("last_hit_at")
        if isinstance(_hit, (int, float)) and time.time() - _hit < 7 * 86400:
            usage_note = (f"   ⚠️ **本週已撞過 Claude 用量上限（{_ust.get('last_hit_local', '?')}，先.一二一-3）**："
                          "補件只排 ①資料錯 ②畫面問題 ③研究，**暫停 ④文書核對**類。\n")
    except Exception:  # noqa: BLE001
        usage_note = ""
    # 先.一二七-A：一輪只戴一頂帽子（CLAUDE.md 九）。研究類帶研究紀律；連續做多項時只接同帽的下一項。
    _is_research = item_class(text) == "研究"
    hat_block = research_hat_block(crunch) if _is_research else dev_hat_block(crunch)
    _t0 = datetime.now(TZ)
    _wrap_at = (_t0 + timedelta(minutes=WRAP_UP_MIN)).strftime("%H:%M")
    prompt = f"""全程繁體中文。你是 Alpha 專案的開發佇列自走輪次（無人值守，沒有人在旁邊看）。
這一輪的 cycle_id 是 `{cycle_id}`（這是實際值，不是佔位符，直接照抄）。

## 時間上限（先.九十三-3）
本輪 {_t0.strftime("%H:%M")} 開工，**{_wrap_at}（{WRAP_UP_MIN} 分鐘）一到就收尾**——外層 60 分鐘會強制砍掉，砍掉的話沒存的進度全丟。
長時間抓取（SIC、Tiingo、SEC、FinMind 分批等）：
1. 開工就用 `date` 記下時間；抓取迴圈每批之間檢查時間，到 {_wrap_at} 就停止送新請求；
2. 已抓到的一律寫進快取／輸出檔，並記下斷點（下一批從哪裡開始）；
3. commit＋push 已完成的部分，PENDING_QUEUE 那一項**維持 `- [ ]`**，補記「第 N 批完成、尚餘多少、下一輪從哪裡續」；
4. 不要為了趕時間跳過冒煙或驗證；時間不夠就把驗證留到下一輪，照實寫「未驗證」。

## 這一輪要做的事
`C:\\alpha\\alpha-app\\PENDING_QUEUE.md` 頂端「執行順序（權威清單）」取到的下一項：

    {clean}
{prev}
{multi}

{hat_block}

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
   補入時標「[自走補入]」與來源出處，不需要事先請示。
   **收工自動補件（2026-10-14 總司令【先.九十五】8，取代先.八十二 8⑦ 的「只限兩種來源」）**：
   每輪**收工前**重算一次——`- [ ]` 少於 12 項，**或** DevQueue 可執行（非[研究]、非互動視窗、
   不被守門員擋）少於 6 項，就自動補件，補到兩個門檻都達到。來源依序：
   ① `BACKLOG.md` 未完成項 ② `docs/UX_REDESIGN_PROPOSAL.md` 未做的 App 項目
   ③ Cowork 全檢報告（2026-10-11，條目已抄在 `PENDING_QUEUE.md`「先.八十　全檢修正」節）未完成項
   ④ `research/DATA_GAP_PLAN.md` 甲類（免費可抓）未做項。**每條寫明來源（檔名＋行號或節名）**；
   ⑤ **研究候選（先.一二七-A 2026-10-21 起，原馬拉松補件來源併入）**：`research/GRAVEYARD_AUTOPSY.md`
   第 6 節（6.1 變形方向）、`research/HYPOTHESIS_QUEUE.md` 未跑的假說，補成 `**編號** [研究]` 條目，
   每條寫明「先寫 PREREG、用沒碰過的資料／新市場／新工具事前登記單發、計入 N」，每輪最多補 3 條。
   **排序照檔頭【常規.補件順序】**：①資料缺口／數字錯 → ②使用者看得到的畫面問題 → ③研究室回補與上面⑤研究候選
   → ④BACKLOG 文書核對（每輪最多 3 項）。
   新補的預設標「（DevQueue 可執行）」，真的需要總司令拍板、或要改核心研究檔案的才標互動視窗。
   **不得**用換行統一、自查術語、格式整理這類小事湊數；新的 alpha 試驗**只准**從⑤兩個來源補、且一律事前登記；
   來源都沒有可做的就不補，在收工紀錄照實寫「來源已用盡」。
{usage_note}
## 一定要遵守
1. 先讀 `C:\\alpha\\alpha-app\\CLAUDE.md`（尤其「零之一、停下條件改為白名單」
   「七、資料原則」「七之二、常駐服務發布紀律」「四之二、驗收證據原則」）與
   `C:\\alpha\\CLAUDE.md`（外部 API 頻率上限清單）。
2. 每一項做完都要跑 `node scripts/smoke_test.mjs`，**全過才能 commit**。
3. 動到 `research/alpha_live_server.py` 或 `research/shioaji_quotes.py` 的 commit，
   最後一步必須重啟服務並跑四步驗證（重啟→比對 build sha→OPTIONS 預檢→stale_process=false）。
4. 做完一項就把 PENDING_QUEUE 那一行從 `- [ ]` 改成 `- [x]` 並補上做了什麼、證據是什麼。
{progress_rule}
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
{block_rule}

## 誠實要求
- 沒驗過的不要說「已完成」，寫「已實作但未驗證」。
- 查不到資料就照 CLAUDE.md 的三來源查證紀律，列出查了哪三個來源。
- 不准為了讓測試過而放寬測試。
"""
    PROMPT_OUT.write_text(prompt, encoding="utf-8", newline="\n")
    try:  # 先.六十四：記下這次派出去的是哪一項，趕工迴圈據此逐項結算（不再用 find_next 猜）
        _st = _load_state()
        _st["_current"] = key
        _save_state(_st)
    except Exception as e:  # noqa: BLE001
        _safe_print(f"WARN_DETECTOR_CRASHED: 記錄 _current 失敗（{type(e).__name__}）")
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
    if cmd == "record_own_dirty":
        return record_own_dirty()
    if cmd == "block":
        return mark_blocked(sys.argv[2] if len(sys.argv) > 2 else "未說明原因")
    if cmd in ("ok", "fail"):
        return record(cmd)
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
