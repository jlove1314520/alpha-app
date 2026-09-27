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

**判定邏輯沿革**：2026-09-26【警.一】原版只用 DevQueue 的 commit 當停擺判定
依據（IBKR 只記錄不判定）。2026-09-27【查.一】查出根因——`dev_queue_runner.py`
的碰撞防護機制（`_recent_real_dirty_reason()`）在互動視窗長時間編輯非機器
寫入檔案時會正確 YIELD 避免衝突，但 YIELD 分支在進入會 commit 心跳的
`finally` 區塊之前就 `exit 0`，導致 DevQueue 心跳在互動視窗做研究工作時
容易假性中斷。當時提出兩個修正方案：A（讓 YIELD 分支也 commit 心跳）、
B（判定改成三軌任一有心跳即存活）。**2026-09-27【乾.三主體第八點】總司令
裁示不採方案 A**（互動視窗編輯檔案時讓 DevQueue 去 commit，會跟互動視窗
自己的 git 操作搶著寫，重演 round607 那種 stash-pop 衝突根因），**改採方案
B 強化版**：判定來源改成「DevQueue／Marathon／Hypothesis-queue 三軌任一
有新鮮心跳（≤60分鐘）即視為本機整體存活」，同時保留個別軌道層級的
`track_stalled` 警告（>360分鐘），讓「機器整體活著」跟「某一條軌道真的
自己停了」分開回答，不互相掩蓋。IBKR quotes 仍維持原設計只記錄不判定
——它有兩個已知、非故障的空窗：(1) 只在美股盤中時段才有新資料；
(2) IBKR Gateway 每週日 01:00 ET 權杖過期需要人工登入，見 CLAUDE.md「IBKR
Gateway/TWS」段落，這段空窗長達數小時到數天，若拿它當判定依據會製造大量
假警報。

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

# 2026-09-27【乾.三主體第八點】總司令裁示：不採方案A（互動視窗編輯檔案時
# 讓DevQueue的YIELD分支也commit心跳，會在互動視窗正做git相關操作時跟它
# 搶著commit，重演round607那種stash-pop衝突根因），改採方案B強化版——
# 判定來源從「只看DevQueue」改成「三軌（DevQueue／Marathon／Hypothesis-
# queue）任一有新鮮心跳即視為本機存活」，同時保留個別軌道層級的
# track_stalled警告（>360分鐘=6小時），讓「機器整體有沒有活著」跟
# 「某一條軌道是不是真的自己停了」這兩個問題分開回答，不互相掩蓋。
TRACK_STALL_THRESHOLD_MIN = 360  # 個別軌道層級警告門檻（6小時），跟上面
# 60分鐘的「本機整體存活」門檻是兩個不同層級的判斷，不是同一個數字。

# 三條本機排程各自的commit message特徵樣式（實測抓自git log，見PENDING_QUEUE.md
# 「警.一」／「乾.三」條目的查證紀錄）。用search不是match，因為都會夾帶
# cycle_id/時間戳等變動內容。
DEVQUEUE_PATTERN = re.compile(r"DevQueue cycle log 自動更新")
MARATHON_PATTERN = re.compile(r"Marathon cycle log 自動更新")
HYPOTHESIS_QUEUE_PATTERN = re.compile(r"Hypothesis-queue cycle log 自動更新")
IBKR_PATTERN = re.compile(r"IBKR quotes auto-update")

# 三軌判定用（不含IBKR——IBKR維持警.一原本的設計，只記錄不參與停擺判定，
# 理由見IBKR_PATTERN附近既有註記：盤外時段與每週人工登入空窗會製造假警報）。
JUDGMENT_TRACKS = {
    "devqueue": DEVQUEUE_PATTERN,
    "marathon": MARATHON_PATTERN,
    "hypothesis_queue": HYPOTHESIS_QUEUE_PATTERN,
}


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

    tracks: dict[str, dict] = {}
    for name, pattern in JUDGMENT_TRACKS.items():
        try:
            sha, ts = _git_log(pattern)
        except Exception as e:  # noqa: BLE001 -- 偵測失敗只降級成警告，不得讓排程崩潰（十二節同一套原則）
            print(f"::warning::track心跳查詢失敗（{name}）：{type(e).__name__}: {e}")
            sha, ts = None, None
        minutes = (now - ts).total_seconds() / 60.0 if ts else None
        tracks[name] = {
            "last_commit_sha": sha,
            "last_commit_at": ts.isoformat() if ts else None,
            "minutes_since": round(minutes, 1) if minutes is not None else None,
            "track_stalled": (minutes is None) or (minutes > TRACK_STALL_THRESHOLD_MIN),
        }

    ibkr_sha, ibkr_ts = _git_log(IBKR_PATTERN)
    ibkr_minutes = (now - ibkr_ts).total_seconds() / 60.0 if ibkr_ts else None

    # 方案B強化版：三軌任一minutes_since<60分鐘，就視為「本機這台機器整體
    # 是活著的」——不再只看DevQueue單一訊號，避免互動視窗長時間編輯檔案時
    # DevQueue被碰撞防護正確YIELD（見查.一條目根因）卻沒有心跳可看，被
    # 誤判成「本機停擺」。
    any_alive = any(
        (t["minutes_since"] is not None) and (t["minutes_since"] <= STALL_THRESHOLD_MIN)
        for t in tracks.values()
    )
    stalled = not any_alive

    # 個別軌道層級警告：即使整體判定「本機存活」，某一條軌道自己可能真的
    # 停了超過6小時——這個訊號跟「本機整體停擺」是兩個不同層級的問題，
    # 分開列出，不讓其中一個掩蓋另一個。
    track_stalled_names = [name for name, t in tracks.items() if t["track_stalled"]]

    return {
        "checked_at": now.isoformat(),
        "stall_threshold_minutes": STALL_THRESHOLD_MIN,
        "track_stall_threshold_minutes": TRACK_STALL_THRESHOLD_MIN,
        "tracks": tracks,
        "ibkr_quotes": {
            "last_commit_sha": ibkr_sha,
            "last_commit_at": ibkr_ts.isoformat() if ibkr_ts else None,
            "minutes_since": round(ibkr_minutes, 1) if ibkr_minutes is not None else None,
            "note": "只記錄不判定停擺——盤外時段與IBKR Gateway每週人工登入空窗"
                    "都會讓這個數字變大，那是預期行為不是故障，見本檔案docstring",
        },
        "stalled": stalled,
        "track_stalled": track_stalled_names,
        "judged_by": "any_of_three_tracks",
        "note": "本機排程最後活動時間；2026-09-27【乾.三主體第八點】裁示改為"
                "「DevQueue／Marathon／Hypothesis-queue三軌任一有新鮮心跳"
                "（≤60分鐘）即視為本機整體存活」（取代原本只看DevQueue單一"
                "訊號的版本，因為DevQueue的既有碰撞防護機制在互動視窗長時間"
                "編輯檔案時會正確YIELD但不留心跳，容易誤判——詳見PENDING_"
                "QUEUE.md查.一條目的根因分析）。個別軌道超過"
                f"{TRACK_STALL_THRESHOLD_MIN}分鐘另外標記track_stalled警告，"
                "不影響本機整體存活的判定，但值得單獨留意。偵測放在雲端是"
                "因為本機push被卡住時無法自己通知任何人。",
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
    if result["track_stalled"]:
        print(f"::warning::個別軌道停擺（不影響本機整體存活判定）：{result['track_stalled']}"
              f"（門檻{TRACK_STALL_THRESHOLD_MIN}分鐘）")
    if result["stalled"]:
        minutes_summary = {name: t["minutes_since"] for name, t in result["tracks"].items()}
        print(
            f"::error::本機排程疑似停擺——三軌(DevQueue/Marathon/Hypothesis-queue)"
            f"皆無{STALL_THRESHOLD_MIN}分鐘內的新commit，各軌距今分鐘數：{minutes_summary}"
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
