# -*- coding: utf-8 -*-
"""本機排程停擺偵測（2026-09-26 總司令裁示【警.一】，方向E落地）。

**為什麼要放在雲端**：本機排程一旦被 git stash-pop 衝突卡住，連 push 都推不出去
（見 `PENDING_QUEUE.md` 「git stash-pop 衝突卡住 push 約5小時」事故），本機自己
沒有任何管道能通知總司令。既有的 `scripts/pipeline_freshness.py` /
`build_local_pipeline_health()` 都要讀本機才有的產出檔，在 GitHub Actions runner
上必然拿不到、只能誠實標 unavailable——那條線本身就不可能偵測「本機排程完全
停擺」這件事。這支反過來，只看 **git commit 歷史**（GitHub Actions checkout
一定拿得到，不依賴本機任何檔案），用「最近一次 DevQueue/IBKR 排程留下的 commit
時間戳」當心跳。

**只用 DevQueue 的 commit 當停擺判定依據，IBKR 只記錄不判定**（這是本次裁示裡
「不確定但可還原的技術選擇」，標記 [自行裁量]，理由如下）：
DevQueue（`run-dev-queue-cycle.ps1`）確認 24/7 每日都在跑（含週末，見
commit 歷史 2026-09-20 週日仍有 11 次 cycle commit），是最穩定的「這台機器活著」
訊號。IBKR quotes 有兩個已知、非故障的空窗：(1) 只在美股盤中時段才有新資料；
(2) IBKR Gateway 每週日 01:00 ET 權杖過期需要人工登入，見 CLAUDE.md「IBKR
Gateway/TWS」段落，這段空窗長達數小時到數天，若拿它當停擺判定依據會製造大量
假警報。因此本檔案只把 IBKR 最近一次 commit 時間寫進報告供人參考，
真正觸發 job 失敗的判斷只看 DevQueue。

跑法：`python scripts/check_local_schedule_heartbeat.py`
（需要在 git checkout 過的 repo 內執行，且 `git log` 要抓得到足夠歷史——
呼叫端 workflow 的 checkout 步驟需帶 `fetch-depth` 涵蓋至少數小時份的 commit）。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# 2026-09-19【最優先·三個都是總司令自己造成的故障】三同一套修法：Windows主控台
# 預設cp950編不出commit message裡的中文/UTF-8字元，這裡的print()本身會炸；
# subprocess抓git log輸出也要明講encoding，否則同樣的cp950解碼會直接爆掉
# （而不是印出亂碼——是exception，會讓整支腳本連stalled判定都做不到）。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

REPO_ROOT = Path(__file__).resolve().parent.parent
STATUS_PATH = REPO_ROOT / "data" / "STATUS.json"

STALL_THRESHOLD_MIN = 60  # 裁示原文：「超過60分鐘沒有新commit」

# 兩條本機排程各自的commit message特徵樣式（實測抓自git log，見PENDING_QUEUE.md
# 「警.一」條目的查證紀錄）。用search不是match，因為兩邊都會夾帶cycle_id/時間戳等
# 變動內容。
DEVQUEUE_PATTERN = re.compile(r"DevQueue cycle log 自動更新")
IBKR_PATTERN = re.compile(r"IBKR quotes auto-update")


def _git_log(pattern: re.Pattern, max_scan: int = 2000) -> tuple[str, datetime] | tuple[None, None]:
    """掃最近 max_scan 筆commit，回傳第一個(=最新，因為git log預設新到舊)符合
    pattern的(sha, 已轉為UTC aware的timestamp)。掃不到回傳(None, None)——
    可能是這條排程真的停了非常久（超過max_scan筆其他commit的時間跨度），
    也可能是命名規則已經變了，兩者都要讓呼叫端知道，不能默默當成「正常」。
    """
    out = subprocess.run(
        ["git", "log", f"-n{max_scan}", "--format=%H|%aI|%s"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        encoding="utf-8", errors="replace",
    ).stdout
    for line in out.splitlines():
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        sha, ts_raw, subject = parts
        if pattern.search(subject):
            ts = datetime.fromisoformat(ts_raw).astimezone(timezone.utc)
            return sha, ts
    return None, None


def evaluate() -> dict:
    now = datetime.now(timezone.utc)
    dq_sha, dq_ts = _git_log(DEVQUEUE_PATTERN)
    ibkr_sha, ibkr_ts = _git_log(IBKR_PATTERN)

    dq_minutes = (now - dq_ts).total_seconds() / 60.0 if dq_ts else None
    ibkr_minutes = (now - ibkr_ts).total_seconds() / 60.0 if ibkr_ts else None

    stalled = dq_minutes is None or dq_minutes > STALL_THRESHOLD_MIN

    return {
        "checked_at": now.isoformat(),
        "stall_threshold_minutes": STALL_THRESHOLD_MIN,
        "devqueue": {
            "last_commit_sha": dq_sha,
            "last_commit_at": dq_ts.isoformat() if dq_ts else None,
            "minutes_since": round(dq_minutes, 1) if dq_minutes is not None else None,
        },
        "ibkr_quotes": {
            "last_commit_sha": ibkr_sha,
            "last_commit_at": ibkr_ts.isoformat() if ibkr_ts else None,
            "minutes_since": round(ibkr_minutes, 1) if ibkr_minutes is not None else None,
            "note": "只記錄不判定停擺——盤外時段與IBKR Gateway每週人工登入空窗"
                    "都會讓這個數字變大，那是預期行為不是故障，見本檔案docstring",
        },
        "stalled": stalled,
        "judged_by": "devqueue",
        "note": "本機排程最後活動時間；只看DevQueue的commit心跳判定是否停擺"
                "（理由與IBKR排除原因見本檔案docstring），偵測放在雲端是因為"
                "本機push被卡住時無法自己通知任何人。",
    }


# ---------------------------------------------------------------------------
# 2026-09-26【查.一】二.2：STATUS.json的schedule_health/local_pipeline_health
# 兩區checked_at停在2026-09-15T19:40（11天未更新）卻仍讓人誤讀成「現在還ok」
# ——根因是generate_status_json.py本身沒有掛在任何排程上（純人工/CC手動執行，
# 見查.一條目的查證），沒有東西會定期重跑它去更新這兩區。這裡不是去改
# generate_status_json.py本身（改了也沒用，它不會自己被觸發），而是讓「本來
# 就已經在雲端每30分鐘跑、也已經在讀寫STATUS.json」的這支腳本，順便對這兩區
# 的checked_at做「離現在多久」的新鮮度判定——這是唯一能在「檔案不會自己更新」
# 的前提下，仍然讓過期狀態被看見的位置：檔案生成當下checked_at必然等於生成
# 時刻本身（永遠新鮮），staleness只能由「之後某個會定期執行的東西」在讀取時
# 判定，不能靠生成端自己判定。
# ---------------------------------------------------------------------------
STALE_THRESHOLD_HOURS = 24
STALENESS_WATCHED_KEYS = ("schedule_health", "local_pipeline_health")


def _mark_block_staleness(doc: dict, key: str, now: datetime) -> None:
    block = doc.get(key)
    if not isinstance(block, dict):
        return
    checked_at_raw = block.get("checked_at")
    try:
        if not checked_at_raw:
            block["status"] = "unknown"
            return
        ts = datetime.fromisoformat(str(checked_at_raw))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age_hours = (now - ts.astimezone(timezone.utc)).total_seconds() / 3600.0
        block["status"] = "stale" if age_hours > STALE_THRESHOLD_HOURS else "ok"
        block["status_checked_at"] = now.isoformat()
        block["status_age_hours"] = round(age_hours, 1)
    except Exception as e:  # noqa: BLE001 -- 偵測失敗只降級成警告，不得讓排程崩潰（十二節同一套原則）
        print(f"::warning::新鮮度判定失敗（{key}）：{type(e).__name__}: {e}")
        block["status"] = "unknown"


def _write_into_status_json(result: dict) -> None:
    if STATUS_PATH.exists():
        try:
            doc = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 -- 壞掉的STATUS.json不該讓這支也跟著炸
            doc = {}
    else:
        doc = {}
    doc["local_schedule_heartbeat"] = result
    now = datetime.now(timezone.utc)
    for key in STALENESS_WATCHED_KEYS:
        _mark_block_staleness(doc, key, now)
    STATUS_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    result = evaluate()
    _write_into_status_json(result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["stalled"]:
        dq = result["devqueue"]
        print(
            f"::error::本機排程疑似停擺——DevQueue最近一次commit(sha={dq['last_commit_sha']})"
            f"距今{dq['minutes_since']}分鐘（門檻{STALL_THRESHOLD_MIN}分鐘）"
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
