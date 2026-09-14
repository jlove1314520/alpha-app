# -*- coding: utf-8 -*-
"""額度感知節流（2026-09-15 總司令交辦）。

**背景**：自走引擎（馬拉松／假設佇列）在候選池枯竭時仍照原頻率（30分鐘一輪）
空轉——2026-09-15 實測 `MARATHON_STATE.md` 記錄「候選池連續39輪（487~526）
無新可推進工作單位」，每一輪仍是完整一次 `claude -p` 呼叫，會把週用量額度
燒在「重新確認一次沒有新東西」這種零產出的輪次上，擠壓真正在產出的
DevQueue 交辦線（見 `dev_queue_runner.py`）與盤中資料管線的額度。

**這支模組不判斷「這一項該不該做」**（那是 `dev_queue_runner.py`／各軌自己
在 STATE.md 寫的判斷），**只判斷「這一輪該不該真的觸發」**——排程器仍然每
30 分鐘照樣觸發 wrapper，wrapper 開工前先問這支模組，多數觸發會被這支模組
擋下（印節流理由、不搶鎖、不消耗任何額度），只有真正到了節流間隔才放行。

**節流生效的兩個獨立條件（達一即節流）**：
1. 帳號用量接近週限額：`account.seven_day_utilization >= SEVEN_DAY_THROTTLE`。
   這個數字是帳號層級的（不分軌道），由**馬拉松**每輪從 `claude -p` 的
   `rate_limit_event` 訊息量到（見 `cycle_stats.py` 的 `seven_day_utilization`
   欄位）——馬拉松30分鐘一輪，更新頻率夠用，假設佇列不需要重複量測同一個
   帳號層級的數字。
2. 候選池連續空轉：`<track>.consecutive_no_progress >= NO_PROGRESS_THRESHOLD`。
   「這一輪有沒有產出」用**機器可查**的訊號判斷，不依賴各軌自己在 STATE.md
   寫的敘述文字（那是給人看的，措辭可能漂移，例如「無新工作單位」和「維持
   同一狀態」是兩種不同寫法，regex 兩邊都要顧到反而更脆弱），也不能用「這
   一輪有沒有commit」判斷——**每一輪不管有沒有實質進度都會commit一次自己的
   STATE.md/REPORT.md紀錄**，用commit本身當訊號永遠是True，量不出差異
   （這是第一版寫完立刻拿真實cycle測出來的，見下方測試紀錄）。改用
   `research/TRIALS_REGISTRY.jsonl`（CLAUDE.md 七之三規定「每個機制×一組
   參數點都要登記進試驗資料庫」，馬拉松與假設佇列兩軌都用同一份檔案登記）
   在這一輪的時間窗（cycle start~end）內**有沒有被新增過任何一行**當統一
   訊號——這份檔案是全專案對「這輪算不算真的推進了研究」的權威登記點，比
   自己另外定義一套判準更貼近專案本來的定義，而且兩軌通用、不用各寫一套。
   代價：純基礎設施修復或查證類的一輪即使有實質價值，只要沒登記新試驗，
   也會被算作「無進度」——這個方向的誤差是「可能節流一輪原本值得跑的維護
   工作」，不是「漏掉真正該做的候選挖掘」，可接受。

**節流生效時的行為**：把「這一輪該不該真的觸發」的門檻從 30 分鐘拉到
`THROTTLED_INTERVAL_MINUTES`（120 分鐘）。DevQueue 交辦線完全不呼叫這支
模組——維持原頻率不降，因為交辦是總司令直接下的指令，額度該優先給它。

用法（wrapper 呼叫，不是給人手動跑的）：
    python quota_throttle.py should_run --track marathon
        # exit 0＝該跑，exit 1＝節流中該讓路，兩者都會印理由
    python quota_throttle.py record --track marathon --window START,END --jsonl <cycle.jsonl>
        # 馬拉松跑完之後呼叫；--jsonl 額外用來取 seven_day_utilization（帳號層級用量）
    python quota_throttle.py record --track hypothesis_queue --window START,END
        # 假設佇列跑完之後呼叫，沒有 jsonl（純文字模式跑 claude -p），不取用量，
        # 只判斷 TRIALS_REGISTRY.jsonl 這段時間窗內有沒有新增
START/END 都是 ISO 時間字串（wrapper 自己記的 cycle 開始/結束時間）。
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # C:\alpha\alpha-app
RESEARCH = Path(__file__).resolve().parent
STATE_PATH = RESEARCH / "data" / "quota_throttle_state.json"
TZ = timezone(timedelta(hours=8))

SEVEN_DAY_THROTTLE = 0.90          # 帳號週用量達 90% 視為「接近週限額」
NO_PROGRESS_THRESHOLD = 5          # 連續 5 輪沒有真的 commit 過東西，視為候選池空轉
NORMAL_INTERVAL_MINUTES = 30       # 排程原本的觸發頻率（兩軌目前都是30分鐘）
THROTTLED_INTERVAL_MINUTES = 120   # 節流時拉長到的頻率


def _load_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(d: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def _now() -> datetime:
    return datetime.now(TZ)


def _is_throttled(state: dict, track: str) -> tuple[bool, str]:
    account = state.get("account", {})
    util = account.get("seven_day_utilization")
    if util is not None and util >= SEVEN_DAY_THROTTLE:
        return True, f"帳號週用量已達{util:.0%}（門檻{SEVEN_DAY_THROTTLE:.0%}），節流保留額度給交辦與資料管線"
    n = state.get(track, {}).get("consecutive_no_progress", 0)
    if n >= NO_PROGRESS_THRESHOLD:
        return True, f"{track}連續{n}輪沒有真的commit過東西，判定候選池空轉，節流"
    return False, ""


def should_run(track: str) -> int:
    state = _load_state()
    throttled, reason = _is_throttled(state, track)
    interval = THROTTLED_INTERVAL_MINUTES if throttled else NORMAL_INTERVAL_MINUTES
    last_at = state.get(track, {}).get("last_actual_run_at")
    if last_at:
        elapsed_min = (_now() - datetime.fromisoformat(last_at)).total_seconds() / 60.0
        if elapsed_min < interval:
            mode = "節流中" if throttled else "正常頻率"
            print(f"SKIP: {mode}，距上次實跑{elapsed_min:.1f}分鐘 < {interval}分鐘門檻"
                  + (f"（{reason}）" if throttled else ""))
            return 1
    if throttled:
        print(f"RUN（節流狀態，但已達{interval}分鐘門檻，本輪照跑）：{reason}")
    else:
        print("RUN: 未達節流條件，正常頻率")
    return 0


TRIALS_REGISTRY = ROOT / "research" / "TRIALS_REGISTRY.jsonl"


def _git(args: list[str]) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace").stdout


def _made_progress(start_s: str, end_s: str) -> bool:
    """這段時間窗內，TRIALS_REGISTRY.jsonl 有沒有被 commit 新增過任何一行。"""
    log = _git(["log", f"--since={start_s}", f"--until={end_s}", "--oneline", "--", str(TRIALS_REGISTRY.relative_to(ROOT))])
    return bool(log.strip())


def record_cycle(track: str, window: str, jsonl_path: str | None) -> int:
    start_s, end_s = window.split(",", 1)
    made_progress = _made_progress(start_s, end_s)
    state = _load_state()
    track_state = state.setdefault(track, {"consecutive_no_progress": 0})
    track_state["consecutive_no_progress"] = 0 if made_progress else track_state.get("consecutive_no_progress", 0) + 1
    track_state["last_actual_run_at"] = _now().isoformat()

    util_note = ""
    if jsonl_path:
        sys.path.insert(0, str(RESEARCH))
        import cycle_stats  # noqa: E402 -- 同目錄下既有的 jsonl 分析工具，重用它的解析邏輯
        res = cycle_stats.analyze(Path(jsonl_path))
        if res.get("seven_day_utilization") is not None:
            state["account"] = {
                "seven_day_utilization": res["seven_day_utilization"],
                "five_hour_utilization": res.get("five_hour_utilization"),
                "measured_at": _now().isoformat(),
                "measured_by_track": track,
            }
            util_note = f" seven_day_utilization={res['seven_day_utilization']}"

    _save_state(state)
    print(f"RECORDED {track}: made_progress={made_progress} "
          f"consecutive_no_progress={track_state['consecutive_no_progress']}{util_note}")
    return 0


def main() -> int:
    args = sys.argv[1:]
    cmd = args[0] if args else ""

    def _opt(name: str) -> str | None:
        if name in args:
            i = args.index(name)
            if i + 1 < len(args):
                return args[i + 1]
        return None

    track = _opt("--track")
    if cmd == "should_run":
        if not track:
            print("usage: quota_throttle.py should_run --track <marathon|hypothesis_queue>")
            return 2
        return should_run(track)
    if cmd == "record":
        window = _opt("--window")
        if not track or not window:
            print("usage: quota_throttle.py record --track <marathon|hypothesis_queue> --window START,END [--jsonl <path>]")
            return 2
        return record_cycle(track, window, _opt("--jsonl"))
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
