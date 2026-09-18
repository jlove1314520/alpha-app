# -*- coding: utf-8 -*-
r"""額度感知節流（2026-09-15 總司令交辦）。

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

**每日用量日誌**（2026-09-15，省額度第一步觀察期）：`should_run()` 每次
被呼叫都會記一筆決定（skip_signal／skip_interval／run），跨日時自動把
前一天的累計寫成一行 append 進 `research/quota_usage_daily.log`——
不用另外跑聚合腳本，這份 log 本身就是「一天一行」的歷史，供總司令一週後
判斷要不要做第二步（換模型）。

**2026-09-17（總司令裁示【接上最後一哩】）補記**：這支機制本身在
2026-09-15上線當下就已經寫好（不是這次才補實作），第一行遲遲沒出現
單純是因為要等第一次「跨日」才會觸發flush（見上方`_record_daily()`），
2026-09-16→09-17跨日時已實測寫出`marathon`那行。**這個檔案沒有像
market.yml那種寫死在workflow裡的`git add`清單**——marathon／
hypothesis_queue兩軌沒有腳本層級的固定commit步驟，是each輪`claude -p`
session自己依CLAUDE.md「收工序」規則commit，所以真正的「加進清單」動作
是：把這個檔案第一次`git add`進版控變成tracked（已於2026-09-17完成），
之後它的異動會被這兩軌各自收工時的例行commit自然帶到，不需要另外維護
一份逐檔清單——跟`scripts/dev_queue_runner.py::MACHINE_WRITTEN`的
regex前綴規則（`^research/[^/]+\.log$`已涵蓋這個檔案）是同一套精神。
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # C:\alpha\alpha-app
RESEARCH = Path(__file__).resolve().parent
STATE_PATH = RESEARCH / "data" / "quota_throttle_state.json"
TRIALS_REGISTRY = RESEARCH / "TRIALS_REGISTRY.jsonl"
# 2026-09-18（Cowork「修我自己造成的節流死鎖」）：_made_progress()原本只認
# TRIALS_REGISTRY.jsonl有沒有新增列，但總司令另外明令重構.B/C/D這批工作
# （描述性研究/PENDING_CALIBRATION）不准寫TRIALS_REGISTRY——這是總司令自己
# 兩條指令彼此矛盾造成的死鎖，不是節流器判斷錯，但節流器要負責修好它：
# 今天6筆真實commit全部被判made_progress=False，consecutive_no_progress
# 衝到12/13，觸發120分鐘節流。改成OR訊號：TRIALS_REGISTRY.jsonl或這個
# 新檔案，任一有新增就算有進度。這個檔案只記「有沒有在動」不記統計判定，
# 不會污染TRIALS_REGISTRY的純度。各輪`claude -p` session要在收工前自己
# append一行（見MARATHON_CONTINUATION_PROMPT.txt／HYPOTHESIS_QUEUE_
# CONTINUATION_PROMPT.txt新增的第零之一步），quota_throttle.py只負責檢查。
PROGRESS_HEARTBEAT = RESEARCH / "PROGRESS_HEARTBEAT.jsonl"
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
        return True, f"{track}連續{n}輪TRIALS_REGISTRY.jsonl沒有新增過東西，判定候選池空轉，節流"
    return False, ""


# 2026-09-15（總司令交辦「先砍不必要的LLM呼叫，再談換模型」）：候選池連續
# 空轉時，即使到了節流後的120分鐘間隔，也不該每次都重新叫一次claude -p去
# 「重新確認一次還是沒有新東西」——那正是燒掉4天額度的元凶（馬拉松連續39輪
# 0新工作單位，每輪仍是一次完整的claude -p呼叫）。這裡加一層更便宜的純
# Python訊號比對：只在consecutive_no_progress>0（已經確認過至少一輪沒進度）
# 時才啟用，比對「這一輪」跟「記錄在案、上次判定沒進度時」這些外部檔案的
# 內容雜湊是否完全相同——完全沒變就代表沒有任何新資訊值得再花一次claude
# 呼叫去重新判斷，直接跳過，連一輪都不叫；只要有任何一個來源變了（不管是
# PENDING_QUEUE.md有新裁示、TRIALS_REGISTRY.jsonl有新登記、還是data/ticks/
# 被動累積了新的一天），才放行讓claude真的跑一輪去判斷這個變化算不算數。
# 刻意排除各軌自己每輪都會寫的敘述性狀態檔（MARATHON_STATE.md／
# HYPOTHESIS_QUEUE.md 的最新輪次段落）——這兩份檔案不管有沒有實質進度，
# 每輪都會被自己的 claude -p session 更新一次（寫進輪次計數器/心得），
# 拿它們當訊號來源等於訊號永遠顯示「有變化」，這支模組就永遠不會觸發
# 跳過，回到跟先前 record_cycle() 用「有沒有commit」當訊號同一種錯誤
# （見 _made_progress 的檔頭說明）。只留「不是這個軌道自己在寫」的來源：
# PENDING_QUEUE.md（人／DevQueue寫）、TRIALS_REGISTRY.jsonl（只在真的
# 登記新試驗時才變，兩軌通用）、data/ticks/（排程被動累積，不是LLM寫的）。
SIGNAL_SOURCES: dict[str, list[Path]] = {
    "marathon": [
        ROOT / "PENDING_QUEUE.md",
        TRIALS_REGISTRY,
        RESEARCH / "data" / "ticks",
    ],
    "hypothesis_queue": [
        ROOT / "PENDING_QUEUE.md",
        TRIALS_REGISTRY,
    ],
}


USAGE_LOG_PATH = RESEARCH / "quota_usage_daily.log"


def _record_daily(track: str, decision: str, detail: str = "") -> None:
    """2026-09-15（總司令交辦，省額度第一步觀察期）：記錄「跳過幾輪／實際
    呼叫claude幾次」，供一週後判斷要不要做第二步（換模型）。`decision` 是
    'skip_signal'（純Python訊號比對跳過，連claude都沒叫）／'skip_interval'
    （間隔未到跳過）／'run'（真的叫了claude -p）三選一。

    2026-09-18（Cowork【重構.B續·先別放棄】三.b修正）：舊版只在跨日時才把
    累計寫成一行append進log，代表「今天」永遠是0筆，同一天內完全看不出
    這一輪剛剛做了什麼決定——這正是總司令昨天在DevQueue踩到的同一種盲點
    搬了家：監控本身的資料要等到事後（跨日）才會出現，事發當下（例如
    停擺100分鐘）什麼都看不到。改成**每次呼叫都立刻append一行**（含時間
    戳、track、decision、detail），不再等到跨日才寫；`quota_throttle_
    state.json`裡的當日累計計數器保留（`skip_signal`/`skip_interval`/
    `run`三個數字），供之後想要「一天一行摘要」時用`--summary`模式重新
    聚合，不用另外重新設計資料結構。"""
    state = _load_state()
    track_state = state.setdefault(track, {})
    today = _now().strftime("%Y-%m-%d")
    daily = track_state.setdefault("daily", {"date": today, "skip_signal": 0, "skip_interval": 0, "run": 0})
    if daily.get("date") != today:
        daily = {"date": today, "skip_signal": 0, "skip_interval": 0, "run": 0}
    daily[decision] = daily.get(decision, 0) + 1
    track_state["daily"] = daily
    state[track] = track_state
    _save_state(state)
    line = f"{_now().isoformat()} {track}: {decision}" + (f"（{detail}）" if detail else "")
    with USAGE_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def daily_summary(track: str | None = None) -> list[str]:
    """把`quota_usage_daily.log`裡逐行記錄的decision，依日期＋track聚合成
    「一天一行」的摘要（2026-09-18新增，補回舊版跨日flush格式被拆成逐行
    記錄後失去的那個檢視方式，供總司令一週後想看趨勢時用）。純讀取，
    不寫檔。"""
    if not USAGE_LOG_PATH.exists():
        return []
    counts: dict[tuple[str, str], dict[str, int]] = {}
    for line in USAGE_LOG_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            ts_part, rest = line.split(" ", 1)
            trk, decision_part = rest.split(": ", 1)
            trk = trk.rstrip(":").strip()
            decision = decision_part.split("（", 1)[0].strip()
            date = ts_part[:10]
        except ValueError:
            continue  # 格式對不上的行（例如舊版跨日摘要行）直接跳過，不讓聚合中斷
        if track and trk != track:
            continue
        key = (date, trk)
        counts.setdefault(key, {"skip_signal": 0, "skip_interval": 0, "run": 0})
        if decision in counts[key]:
            counts[key][decision] += 1
    out = []
    for (date, trk), c in sorted(counts.items()):
        out.append(f"{date} {trk}: skip_signal={c['skip_signal']} skip_interval={c['skip_interval']} run={c['run']}")
    return out


def _signal_hash(track: str) -> str:
    h = hashlib.sha256()
    for p in SIGNAL_SOURCES.get(track, []):
        try:
            if p.is_dir():
                entries = sorted((f.name, f.stat().st_mtime, f.stat().st_size) for f in p.iterdir())
                h.update(repr(entries).encode("utf-8"))
            elif p.exists():
                h.update(p.read_bytes())
        except OSError:
            continue  # 讀不到就跳過這個來源，不讓單一檔案問題擋住整個判斷
    return h.hexdigest()


def should_run(track: str) -> int:
    state = _load_state()
    throttled, reason = _is_throttled(state, track)
    track_state = state.get(track, {})

    # 純Python的「有沒有新訊號」快篩——只有已經確認過至少一輪沒進度時才啟用
    # （見上方模組層級註解），比連calude都不叫更便宜，不佔用should_run的
    # 30/120分鐘間隔判斷，是額外疊加的一層。
    if track_state.get("consecutive_no_progress", 0) > 0:
        current_hash = _signal_hash(track)
        last_hash = track_state.get("last_signal_hash")
        if last_hash is not None and current_hash == last_hash:
            print(f"SKIP: 純Python訊號比對——自上次判定候選池空轉以來，"
                  f"PENDING_QUEUE.md/{track}相關狀態檔/TRIALS_REGISTRY.jsonl 內容完全沒變，"
                  f"沒有新資訊值得再叫一次 claude 重新確認，本輪連 claude -p 都不叫")
            _record_daily(track, "skip_signal", "訊號未變，連claude都沒叫")
            return 1
        # 訊號有變化：記下這次看到的雜湊，讓真正跑的這一輪（或下一次skip判斷）用最新值比對
        track_state["last_signal_hash"] = current_hash
        state[track] = track_state
        _save_state(state)

    interval = THROTTLED_INTERVAL_MINUTES if throttled else NORMAL_INTERVAL_MINUTES
    last_at = state.get(track, {}).get("last_actual_run_at")
    if last_at:
        elapsed_min = (_now() - datetime.fromisoformat(last_at)).total_seconds() / 60.0
        if elapsed_min < interval:
            mode = "節流中" if throttled else "正常頻率"
            print(f"SKIP: {mode}，距上次實跑{elapsed_min:.1f}分鐘 < {interval}分鐘門檻"
                  + (f"（{reason}）" if throttled else ""))
            _record_daily(track, "skip_interval",
                          f"{mode}，距上次實跑{elapsed_min:.1f}分鐘<{interval}分鐘門檻"
                          + (f"，{reason}" if throttled else ""))
            return 1
    if throttled:
        print(f"RUN（節流狀態，但已達{interval}分鐘門檻，本輪照跑）：{reason}")
        _record_daily(track, "run", f"節流狀態但已達門檻，{reason}")
    else:
        print("RUN: 未達節流條件，正常頻率")
        _record_daily(track, "run", "正常頻率")
    return 0


def _git(args: list[str]) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace").stdout


def _made_progress(start_s: str, end_s: str) -> bool:
    """這段時間窗內，TRIALS_REGISTRY.jsonl **或** PROGRESS_HEARTBEAT.jsonl
    有沒有被 commit 新增過任何一行（任一即算有進度，2026-09-18修正——原本
    只認TRIALS_REGISTRY，但總司令明令重構.B/C/D這類描述性研究不准寫
    TRIALS_REGISTRY，結構上不可能產生那個訊號，兩條指令互相矛盾造成
    節流死鎖，見PROGRESS_HEARTBEAT定義處的說明）。"""
    for path in (TRIALS_REGISTRY, PROGRESS_HEARTBEAT):
        log = _git(["log", f"--since={start_s}", f"--until={end_s}", "--oneline", "--", str(path.relative_to(ROOT))])
        if log.strip():
            return True
    return False


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
    if cmd == "summary":
        # 給人手動查「一天一行」摘要用，2026-09-18新增，見daily_summary()
        for line in daily_summary(track):
            print(line)
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
