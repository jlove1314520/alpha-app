"""Shared FinMind fetch + local parquet cache layer for the research pipeline.

**Strategy/analysis code must never call _fetch() directly.** The one sanctioned
entry point is load_dev() below, which always caps at VAL_END -- per
CONSTITUTION.md, "資料載入預設就截斷在 holdout 邊界前". _fetch() is the raw,
uncapped primitive; it exists only so load_dev() and load_full_history() (the
one legitimate path to holdout data, used exclusively to feed
validation.holdout.unlock_holdout_once()) have something to build on.

This split exists because a Cowork audit (2026-08-22) found that the original
single fetch() function had no cap at all -- validation.holdout.cap_to_dev()
was opt-in, so any research code that fetched data and forgot to filter it
would silently get holdout rows mixed into what looked like ordinary data.
See STRATEGY_LOG.md's 2026-08-22 entry on this for the full incident writeup.

Caching, independent of the above: every dataset pull should go through one
of the functions in this module, for two reasons:
  1. FinMind's free tier has a rate limit (see DATA.md) -- re-fetching the
     same range on every script run burns quota for nothing.
  2. The cached parquet file under research/data/raw/ IS the audit trail:
     any number downstream can be traced back to the exact raw response it
     came from, by filename.

This deliberately does NOT try to be a smart incremental cache (merging new
date ranges into existing files, deduping, etc). Caching is keyed on the
exact (dataset, data_id, start_date, end_date) request. Ask for a different
range and you get a new cache file, possibly with overlapping data. That is
wasteful of disk but never wrong -- a dumb cache you can trust beats a clever
one that might silently serve stale-and-wrong data. Revisit if disk usage
ever actually becomes a problem.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests


def _atomic_read_parquet(path: Path) -> pd.DataFrame:
    """2026-08-29新增（determinism_self_test.py實測發現，配對`_atomic_to_
    parquet()`）：即使寫入是atomic的，讀取端在另一個process剛好正在
    `os.replace()`換名的那個瞬間去開檔，Windows偶爾還是會回傳
    PermissionError（不是資料損毀，是暫時性檔案鎖狀態——這個瞬間本身
    極短，重試立刻就會成功）。加短重試，讀取端才不會因為這個暫時性
    windows檔案系統狀態就整支腳本意外中止。"""
    for attempt in range(20):
        try:
            return pd.read_parquet(path)
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.05 * (attempt + 1))


def _atomic_to_parquet(df: pd.DataFrame, path: Path) -> None:
    """2026-08-29新增（可重現性稽核發現的真bug）：`df.to_parquet(path)`本身
    不是atomic的——如果兩個process同時fetch同一個尚未快取的(dataset,
    data_id, start_date, end_date)組合（例如這個process跟同時在跑的
    AlphaMarathon背景迴圈），兩邊都會判斷「快取不存在」而各自發送請求、
    各自寫入同一個路徑，寫入過程中互相interleave可能產生截斷/損毀的
    parquet檔，導致「同輸入、不同次執行讀到不同（甚至讀取失敗）的資料」
    ——這正是回測不可重現的根因候選之一。修法：每個process寫進自己專屬
    的臨時檔（檔名帶pid+uuid，不會撞名），寫完才用`os.replace()`原子性
    地換名成正式路徑——`os.replace()`在同一個檔案系統上是atomic的
    （POSIX/Windows皆然），並發的讀取者只會讀到「完全新」或「完全舊」
    的檔案，不會讀到寫一半的檔案；兩個process同時寫，最後贏的那個換名
    生效，但因為兩邊寫的都是同一個API呼叫算出的同樣資料，內容不會不一致，
    差別只在誰先誰後贏得換名，不影響正確性。"""
    tmp_path = path.with_name(f"{path.name}.tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}")
    df.to_parquet(tmp_path, index=False)
    # 2026-08-29新增（determinism_self_test.py實測發現）：Windows的os.replace()
    # 在另一個process剛好也在讀/寫同一個目標路徑時，偶爾會拋PermissionError
    # （[WinError 5]拒絕存取，跟POSIX rename()不同，POSIX不受open file handle
    # 影響）——實測4個並發writer各30次寫入中出現4次，是暫時性的檔案鎖，不是
    # 資料損毀（reader全程沒讀到任何壞資料，見determinism_self_test.py Test A
    # 結果），重試幾次就會過。加短重試，避免這個Windows特有的暫時性錯誤讓
    # 呼叫端整支腳本意外中止。
    for attempt in range(20):
        try:
            os.replace(tmp_path, path)
            return
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.05 * (attempt + 1))

DATA_DIR = Path(__file__).parent / "data" / "raw"
DATA_DIR.mkdir(parents=True, exist_ok=True)

FM_BASE = "https://api.finmindtrade.com/api/v4/data"

# 2026-08-28 大幅升級（使用者裁示「428是我們自己打出來的」，「資料源禮儀」
# 三條規則）：2026-08-27加的0.35秒節流只是「同一個process內」的in-memory
# 節流——2026-08-27晚到2026-08-28整晚的真實incident（IP banned 403、
# quota exhausted 402各發生過至少兩次）證明這完全不夠：那一晚是好幾支
# 「各自獨立process」的腳本（build_price_history.py／update_price_history.py／
# backfill_price_history_gaps.py／這支client餵給的各research腳本）先後或
# 交錯執行，每個process的_last_call_ts都是從0開始算，互相之間完全沒有
# 協調，短時間內疊加起來的真實請求頻率遠比任何單一process自己的節流數字
# 高很多。改用**跨process共用的檔案狀態**（`data/rate_limit_state.json`，
# 跟`.github/scripts/`那邊的request_guard.py共用同一份schema、各自複製一份
# 邏輯──跨repo/跨目錄不import是既有慣例，見其他腳本docstring）：
# - 間隔從0.35秒拉長到3秒（使用者明確指定的下限）。
# - 新增斷路器：收到428/403就把這個來源標記「封鎖中，至少2小時內不再打」，
#   寫進共用狀態檔，讓其他process（不管是不是同一支腳本）也會看到並遵守。
# - `generate_status_json.py`會把這份狀態檔的內容併進`data/STATUS.json`，
#   使用者/協作者都看得到目前哪些來源被封鎖、封鎖到什麼時候。
RATE_LIMIT_STATE_PATH = Path(__file__).parent.parent / "data" / "rate_limit_state.json"
RATE_LIMIT_MIN_INTERVAL_SEC = 3.0
RATE_LIMIT_BLOCK_SECONDS = 2 * 60 * 60
SOURCE_KEY = "finmind"


def _load_rate_limit_state() -> dict:
    if RATE_LIMIT_STATE_PATH.exists():
        try:
            return json.loads(RATE_LIMIT_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"sources": {}}


def _save_rate_limit_state(state: dict) -> None:
    RATE_LIMIT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    RATE_LIMIT_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _rate_limit_wait_or_raise(source: str = SOURCE_KEY) -> None:
    """真正發送請求前一定要呼叫。如果這個來源目前在封鎖冷卻中，直接拋
    RuntimeError（不要讓呼叫端誤以為「沒資料」，這是「不能問」不是「問了沒有」，
    兩者對下游的意義完全不同，不能混淆）。沒被封鎖的話，確保跟上次真正
    發出的請求間隔至少`RATE_LIMIT_MIN_INTERVAL_SEC`秒，不夠就在這裡sleep。"""
    state = _load_rate_limit_state()
    src = state["sources"].get(source, {})
    now = time.time()
    blocked_until = src.get("blocked_until")
    if blocked_until and now < blocked_until:
        remain_min = round((blocked_until - now) / 60, 1)
        raise RuntimeError(
            f"{source} 目前處於封鎖冷卻中（還剩約{remain_min}分鐘，"
            f"原因：{src.get('block_reason', '未知')}），依「資料源禮儀」規則拒絕發送請求"
        )
    last = src.get("last_request_at")
    if last and (now - last) < RATE_LIMIT_MIN_INTERVAL_SEC:
        time.sleep(RATE_LIMIT_MIN_INTERVAL_SEC - (now - last))
    src["last_request_at"] = time.time()
    state["sources"][source] = src
    _save_rate_limit_state(state)


def _rate_limit_record_block(source: str, status_code: int, detail: str = "") -> None:
    """收到428/403後呼叫，把這個來源標記成封鎖中，讓所有process（不限
    這支腳本）都會透過共用狀態檔看到並停止繼續打這個來源。"""
    state = _load_rate_limit_state()
    src = state["sources"].setdefault(source, {})
    src["blocked_until"] = time.time() + RATE_LIMIT_BLOCK_SECONDS
    src["block_reason"] = f"HTTP {status_code}" + (f" {detail}" if detail else "")
    src["blocked_at"] = datetime.now(timezone.utc).isoformat()
    _save_rate_limit_state(state)


def _throttle() -> None:
    """舊名稱保留相容（_fetch()內部呼叫點沿用這個名字），內容已經改成
    上面跨process共用的版本，不再是單純in-memory節流。"""
    _rate_limit_wait_or_raise(SOURCE_KEY)


def _cache_path(dataset: str, data_id: str, start_date: str, end_date: str | None) -> Path:
    id_part = data_id or "ALL"
    end_part = end_date or "latest"
    safe = lambda s: str(s).replace("/", "-").replace("\\", "-")
    return DATA_DIR / f"{safe(dataset)}__{safe(id_part)}__{safe(start_date)}__{safe(end_part)}.parquet"


def _fetch(
    dataset: str,
    data_id: str = "",
    start_date: str = "2000-01-01",
    end_date: str | None = None,
    force_refresh: bool = False,
    max_retries: int = 3,
    timeout: float = 15.0,
) -> pd.DataFrame:
    """Raw, uncapped fetch of one FinMind dataset, cached to parquet.

    INTERNAL. Do not call this from strategy/analysis code -- use load_dev()
    instead. This has no holdout protection whatsoever; it will happily
    return rows past VAL_END if you ask it to (start_date/end_date exactly as
    given, no clamping).

    Raises RuntimeError if every retry fails -- callers should not silently
    treat a fetch failure as "no data" (that was the App's old bug pattern;
    the research pipeline holds itself to a higher bar than the phone UI).
    """
    path = _cache_path(dataset, data_id, start_date, end_date)
    if path.exists() and not force_refresh:
        return _atomic_read_parquet(path)

    params = {"dataset": dataset, "start_date": start_date}
    if data_id:
        params["data_id"] = data_id
    if end_date:
        params["end_date"] = end_date

    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            _throttle()  # 這裡如果目前在封鎖冷卻中會直接RuntimeError，不會發出請求
            resp = requests.get(FM_BASE, params=params, timeout=timeout)
            if resp.status_code in (402, 403, 428, 429):
                # 2026-08-28新增：這幾個狀態碼是「額度用盡/被封鎖/請求過快」，不是
                # 「這個dataset本來就查不到」——重試只會讓封鎖更久，這裡立刻把這個
                # 來源標記封鎖2小時（見_rate_limit_record_block()），讓其他process
                # 也會透過共用狀態檔看到並停手，不是只有這個process自己記得。
                _rate_limit_record_block(SOURCE_KEY, resp.status_code, resp.text[:200])
                raise RuntimeError(
                    f"FinMind回應HTTP {resp.status_code}（額度/封鎖類錯誤，已標記{SOURCE_KEY}"
                    f"封鎖{RATE_LIMIT_BLOCK_SECONDS//3600}小時，見{RATE_LIMIT_STATE_PATH}）："
                    f"dataset={dataset} data_id={data_id} -- {resp.text[:300]}"
                )
            if 400 <= resp.status_code < 500:
                # Client error (bad dataset name, bad params, paid-tier gate) -- this will
                # never succeed on retry, so fail fast instead of burning the retry budget.
                raise RuntimeError(
                    f"FinMind rejected the request (HTTP {resp.status_code}): "
                    f"dataset={dataset} data_id={data_id} -- {resp.text[:300]}"
                )
            resp.raise_for_status()
            body = resp.json()
            break
        except RuntimeError:
            raise
        except Exception as e:  # noqa: BLE001 -- network/5xx/timeout: worth retrying
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    else:
        raise RuntimeError(
            f"FinMind fetch failed after {max_retries} attempts: "
            f"dataset={dataset} data_id={data_id} start={start_date} end={end_date} ({last_err})"
        )

    if isinstance(body, dict) and body.get("status") not in (200, None):
        raise RuntimeError(
            f"FinMind returned status={body.get('status')} msg={body.get('msg')!r} "
            f"for dataset={dataset} data_id={data_id} -- not caching this as if it were valid data"
        )

    data = body.get("data", []) if isinstance(body, dict) else []
    df = pd.DataFrame(data)
    _atomic_to_parquet(df, path)
    return df


def load_dev(
    dataset: str,
    data_id: str = "",
    start_date: str = "2000-01-01",
    end_date: str | None = None,
    date_col: str = "date",
    force_refresh: bool = False,
) -> pd.DataFrame:
    """THE sanctioned entry point for strategy/analysis code. Always returns
    data capped at VAL_END or earlier -- no row with `date_col` > VAL_END can
    ever come back from this function, full stop.

    `end_date`, if given, further narrows the window (e.g. for a walk-forward
    test that wants dev data only up to some earlier date) but can never
    widen past VAL_END -- passing an end_date after VAL_END is silently
    clamped down to VAL_END, not honored.

    If the underlying dataset has no `date_col` column (e.g. a dataset that
    isn't time-series shaped), this raises rather than skip the check --
    silently trusting an uncapped fetch because "this one probably doesn't
    need it" is exactly the class of assumption that caused the original
    leak. Pass a correct date_col, or use _fetch() directly with a code
    comment explaining why this dataset is exempt.
    """
    from validation.holdout import VAL_END  # local import: avoids a hard import-order

    # requirement between finmind_client and validation at module-load time
    effective_end = end_date if (end_date and end_date <= VAL_END) else VAL_END
    df = _fetch(dataset, data_id, start_date, effective_end, force_refresh=force_refresh)
    if df.empty:
        return df
    if date_col not in df.columns:
        raise ValueError(
            f"load_dev(dataset={dataset!r}): no {date_col!r} column to enforce the holdout cap on. "
            "Either pass the correct date_col, or this dataset genuinely isn't a capped time series "
            "and should be fetched with _fetch() directly (with a comment explaining why)."
        )
    # _fetch already asked FinMind for <= effective_end, but re-filter defensively in case the
    # API ever ignores end_date for some dataset -- belt and suspenders, per the whole point of this fix.
    return df[df[date_col] <= effective_end].reset_index(drop=True)


def load_full_history(
    dataset: str,
    data_id: str = "",
    start_date: str = "2000-01-01",
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Uncapped fetch, through today. The ONLY legitimate use is to build the
    DataFrame handed to validation.holdout.unlock_holdout_once() during a
    real, one-time holdout evaluation -- that function does its own
    logging/locking and will refuse a second unlock.

    Do not call this to "just get the latest data" for ordinary analysis.
    If you find yourself reaching for this function outside of an actual
    holdout unlock, you almost certainly want load_dev() instead.
    """
    return _fetch(dataset, data_id, start_date, end_date=None, force_refresh=force_refresh)


def clear_cache(pattern: str = "*") -> int:
    """Delete cached parquet files matching a glob pattern. Returns count deleted."""
    n = 0
    for p in DATA_DIR.glob(f"{pattern}.parquet"):
        p.unlink()
        n += 1
    return n
