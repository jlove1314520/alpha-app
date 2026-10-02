"""紙.二：供給緊縮 v2 前進式紙上追蹤（#407，總司令 2026-10-01【先.五】二）。

**這不是回測，也不是新證據。** 假設 v2 源自 #406 登記後的消融結果（docs/PREREG_supply_tightness_v2_FORWARD.md），
只以前進資料判讀。虛擬資金，不下任何真實單；與紙.一（paper_7030_tracker.py）完全獨立。

硬規則（對應 PREREG v2 §8）：
- 任何持股／分數／績效只能在「換股日當下」產生，不得事後補算過去日期：換股日 < 2026-11-16 一律拒絕；
  財報達 98% 入庫即換股；換股日後逾 MAX_LATE 個交易日仍未達 98% → 不跳過，改以當下已入庫者計分
  （未入庫者當季不計分、記錄覆蓋率）；財報或價格覆蓋率 < 80% 才記 skipped_data_unready，沿用既有持股，不補算。
- 紀錄 research/data/paper_supply_v2_log.jsonl 為 append-only；腳本冪等（每筆事件有 key，已存在即不再寫）。
- 資料過期或來源失敗只降級成警告並記錄，不得補猜、不得以估計值替代缺失資料。
- 追蹤期間不得修改任何定義；滿 4 季（2027-11-15 換股日）前報告模式不輸出任何績效數字。

[自行裁量]（見 PROGRESS.md 2026-10-01 紙.二／先.六 條目）：
- 價格與回測同源（先.六-一）：FinMind TaiwanStockPrice 原始價 ＋ research/adjust.py 的事件還原（股利／分割／減資／面額變更，
  由 adjust._combine_adjustment_events 合併），用於 12 個月落後排名、成交價與淨值；成交開盤價另與 data/price_history.json
  （官方 TWSE/TPEx 原始開盤）交叉核對，差異 > 0.5% 記警告。yfinance 只作備援，使用時該筆標記 price_source=fallback。
- 財報用 FinMind 逐檔抓取；訊號資訊集為「換股日之前的收盤」、成交日為訊號後第一個交易日開盤；
  初始虛擬資金 1,000,000 元（只影響顯示，績效與規模無關）。
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import precheck_supply_tightness as pt  # noqa: E402  只借用 _wide/_grid/FINANCIAL/NON_STOCK，同一份指標定義
import supply_tightness_core as core  # noqa: E402
import adjust as adj  # noqa: E402  只借用 _combine_adjustment_events（純函式，與回測同一份還原邏輯）
from pit import statutory_quarterly_pit_date  # noqa: E402

TZ = timezone(timedelta(hours=8))
DATA = HERE / "data"
LOG_PATH = DATA / "paper_supply_v2_log.jsonl"
STATE_PATH = DATA / "paper_supply_v2_state.json"
LOCK_PATH = DATA / "paper_supply_v2.lock"

FIRST_PERIOD = pd.Period("2026Q3", freq="Q")
FIRST_REBALANCE = pd.Timestamp("2026-11-16")
FIRST_INTERPRET = pd.Timestamp("2027-11-15")
TOP_N, HYST, LAG_THR, WEIGHT = 20, 30, 0.60, 0.05
COLS = ["I1", "I2", "I3", "I4"]
MIN_IND = 3
MAX_LATE = 10
WINDOW_BEFORE_DAYS = 30
SETTLED_MIN = 0.98
PRICE_COV_MIN = 0.80
CAPITAL = 1_000_000.0
DEFER_MAX = 10
STMT_DS = (("fs", "TaiwanStockFinancialStatements"), ("bs", "TaiwanStockBalanceSheet"),
           ("cf", "TaiwanStockCashFlowsStatement"))
STMT_START = "2024-01-01"
REFRESH_BUDGET = 200
CLOSE_HHMM = (14, 30)
PRICE_DS = ("TaiwanStockPrice", "TaiwanStockDividend", "TaiwanStockCapitalReductionReferencePrice")
EVENT_DS_ALL = ("TaiwanStockSplitPrice", "TaiwanStockParValueChange")
PRICE_START = "2025-01-01"
XCHECK_TOL = 0.005
PRICE_HISTORY_PATH = HERE.parent / "data" / "price_history.json"
NOTICE = "紙.二為事後假設的前進式追蹤，非證據；滿 8 季前不得作為真錢依據。"


# ───────────────────────── 日曆／換股日 ─────────────────────────
def deadline(p: pd.Period) -> pd.Timestamp:
    return pd.Timestamp(statutory_quarterly_pit_date(p.end_time.normalize()))


def periods_until(until: pd.Timestamp):
    p = FIRST_PERIOD
    while deadline(p) <= until:
        yield p
        p += 1


def rebalance_day(cal: pd.DatetimeIndex, D: pd.Timestamp):
    i = int(cal.searchsorted(D, side="right"))
    return cal[i] if i < len(cal) else None


def target_period(R: pd.Timestamp) -> pd.Period:
    best = None
    for p in pd.period_range("2012Q1", "2040Q4", freq="Q"):
        if deadline(p) < R:
            best = p
        else:
            break
    return best


# ───────────────────────── 季表（與 supply_tightness_panel._quarter_table_fs_tolerant 同定義）─────────────────────────
def quarter_table_from_frames(fs, bs, cf):
    if fs is None or "type" not in fs.columns:
        return None
    f = pt._grid(pt._wide(fs, ["Revenue", "GrossProfit", "CostOfGoodsSold"]))
    if f.empty:
        return None
    bcols = ["TotalAssets", "OtherCurrentLiabilities", "CurrentContractLiabilities", "Inventories"]
    has_bs = bs is not None and "type" in bs.columns and len(bs)
    b = pt._grid(pt._wide(bs, bcols)) if has_bs else pd.DataFrame(columns=bcols)
    idx = f.index.union(b.index)
    f, b = f.reindex(idx), b.reindex(idx)
    if b.empty or not all(c in b.columns for c in bcols):
        b = pd.DataFrame(np.nan, index=idx, columns=bcols)
    q = pd.DataFrame(index=idx)
    ta, ocl, ccl = b["TotalAssets"], b["OtherCurrentLiabilities"], b["CurrentContractLiabilities"]
    prox = (ocl.fillna(0) + ccl.fillna(0)).where(ocl.notna() | ccl.notna())
    q["i1_lvl"] = prox / ta
    ttm = lambda s: s.rolling(4, min_periods=4).sum()  # noqa: E731
    cogs, rev, gp = ttm(f["CostOfGoodsSold"]), ttm(f["Revenue"]), ttm(f["GrossProfit"])
    avg_inv = b["Inventories"].rolling(5, min_periods=5).mean()
    q["i2_lvl"] = cogs / avg_inv
    q["i3_lvl"] = gp / rev
    capex_ttm = pd.Series(np.nan, index=idx)
    if cf is not None and "type" in cf.columns:
        c = pt._grid(pt._wide(cf, ["PropertyAndPlantAndEquipment"])).reindex(idx)["PropertyAndPlantAndEquipment"]
        qn = pd.Series(idx.quarter, index=idx)
        single = c.where(qn == 1, c - c.shift(1))
        capex_ttm = ttm(-single)
    q["i4_lvl"] = capex_ttm / rev.where(rev > 0)
    for k in ("i1", "i2", "i3", "i4"):
        q[k.upper()] = q[f"{k}_lvl"] - q[f"{k}_lvl"].shift(4)
    return q


# ───────────────────────── 訊號 ─────────────────────────
def snapshot_arrays(codes, bars, R: pd.Timestamp):
    """與 Panel.snapshot 同邏輯，但只吃換股日 R 之前的 bar（嚴格 < R）。"""
    d64 = np.datetime64(R)
    lim64 = np.datetime64(R - pd.Timedelta(days=45))
    n = len(codes)
    alive = np.zeros(n, bool)
    p12 = np.full(n, np.nan)
    p60 = np.full(n, np.nan)
    for j, c in enumerate(codes):
        df = bars.get(c)
        if df is None or df.empty:
            continue
        ods = df.index.values.astype("datetime64[ns]")
        k = int(np.searchsorted(ods, d64, side="left"))
        if k == 0 or ods[k - 1] < lim64:
            continue
        alive[j] = True
        adj = df["Adj Close"].values.astype(float)
        if k >= 130:
            last = pd.Timestamp(ods[k - 1])
            tgt = np.datetime64(last - pd.DateOffset(months=12))
            b = int(np.searchsorted(ods, tgt, side="right")) - 1
            if b >= 0:
                p12[j] = adj[k - 1] / adj[b] - 1
        if k > 61:
            p60[j] = adj[k - 1] / adj[k - 61] - 1
    return alive, p12, p60


def build_signal(R, period, uni, tables, bars, prev_codes):
    if R < FIRST_REBALANCE:
        raise ValueError(f"拒絕：換股日 {R.date()} 早於首次換股日 {FIRST_REBALANCE.date()}，不得事後補算過去日期")
    codes = list(uni["code"])
    alive, p12, p60 = snapshot_arrays(codes, bars, R)
    S = {"alive": alive, "p12": p12, "p60": p60}
    for k in COLS:
        v = np.full(len(codes), np.nan)
        for j, c in enumerate(codes):
            t = tables.get(c)
            if t is not None and period in t.index:
                v[j] = t.at[period, k]
        S[k] = v
    P = SimpleNamespace(industry=np.array(list(uni["industry"]), dtype=object))
    F = core.score_frame(P, S, cols=COLS, inc=None, min_ind=MIN_IND)
    cidx = {c: i for i, c in enumerate(codes)}
    prev = [cidx[c] for c in prev_codes if c in cidx]
    sel = core.select(F, prev, "p12", LAG_THR, TOP_N, HYST)
    pool = np.flatnonzero(core.lag_mask(F, "p12", LAG_THR))
    order = pool[np.argsort(-F["score"][pool], kind="stable")]
    rank = {int(F["idx"][o]): i + 1 for i, o in enumerate(order)}
    pos_of = {int(g): i for i, g in enumerate(F["idx"])}
    picks = []
    for g in sel:
        i = pos_of[g]
        picks.append({"code": codes[g], "score": round(float(F["score"][i]), 6), "rank": rank.get(g),
                      "bucket": F["buckets"][int(F["bucket"][i])], "industry": str(uni["industry"].iloc[g]),
                      "I1": _r(S["I1"][g]), "I2": _r(S["I2"][g]), "I3": _r(S["I3"][g]), "I4": _r(S["I4"][g]),
                      "p12": _r(p12[g])})
    return {"picks": picks, "n_universe": len(codes), "n_alive": int(alive.sum()), "n_scored": int(len(F["idx"])),
            "n_pool": int(len(pool)), "n_cash_slots": TOP_N - len(picks)}


def _r(x):
    return None if not np.isfinite(x) else round(float(x), 6)


# ───────────────────────── 模擬（與 supply_tightness_core.Sim 同機制，改成吃 bars 字典）─────────────────────────
def simulate(signals, cal, bars, br, sr, capital=CAPITAL, dm=DEFER_MAX):
    """signals: [{period, after, picks:[code]}]；回傳 None（尚無已啟動的訊號）或結果字典。"""
    T = len(cal)
    acts = []
    for s in sorted(signals, key=lambda s: s["after"]):
        ai = int(cal.searchsorted(s["after"], side="right"))
        if ai < T:
            acts.append((ai, s))
    if not acts:
        return None
    codes = sorted({c for s in signals for c in s["picks"]})
    cidx = {c: i for i, c in enumerate(codes)}
    M = len(codes)
    AO = np.full((T, M), np.nan)
    ACF = np.full((T, M), np.nan)
    RO = np.full((T, M), np.nan)
    RC = np.full((T, M), np.nan)
    LU = np.zeros((T, M), bool)
    LD = np.zeros((T, M), bool)
    for c, j in cidx.items():
        df = bars.get(c)
        if df is None or df.empty:
            continue
        df = df[df["Close"] > 0]
        pos = cal.get_indexer(df.index)
        ok = pos >= 0
        rawc = df["Close"].values.astype(float)
        adj = df["Adj Close"].values.astype(float)
        op = df["Open"].values.astype(float)
        op = np.where(op > 0, op, np.nan)
        hi, lo = df["High"].values.astype(float), df["Low"].values.astype(float)
        fac = adj / rawc
        prev = np.r_[np.nan, rawc[:-1]]
        with np.errstate(invalid="ignore"):
            flat = (op == hi) & (hi == lo) & (op > 0)
            lu = flat & (op >= prev * 1.095)
            ld = flat & (op <= prev * 0.905)
        AO[pos[ok], j] = (op * fac)[ok]
        ACF[pos[ok], j] = adj[ok]
        RO[pos[ok], j] = op[ok]
        RC[pos[ok], j] = rawc[ok]
        LU[pos[ok], j] = lu[ok]
        LD[pos[ok], j] = ld[ok]
    ACFF = pd.DataFrame(ACF).ffill().values
    t0 = acts[0][0]
    sh = np.zeros(M)
    cash = capital
    eq = np.full(T, np.nan)
    sell_orders: dict[int, int] = {}
    buy_orders: dict[int, int] = {}
    fills, expired = [], []
    nxt = 0
    cur_period = acts[0][1]["period"]

    def rec(t, i, side, v, px, rate):
        fills.append({"date": cal[t], "code": codes[i], "side": side, "value": float(v), "px_raw": float(px),
                      "cost": float(v * rate), "period": cur_period})

    for t in range(t0, T):
        if nxt < len(acts) and acts[nxt][0] == t:
            s = acts[nxt][1]
            cur_period = s["period"]
            tgt = [cidx[c] for c in s["picks"]]
            ts = set(tgt)
            for i in np.flatnonzero(sh > 0):
                if int(i) not in ts:
                    sell_orders[int(i)] = t + dm
            for i in list(sell_orders):
                if i in ts:
                    del sell_orders[i]
            for i in buy_orders:
                expired.append({"date": cal[t], "code": codes[i], "reason": "superseded"})
            buy_orders = {i: t + dm for i in tgt}
            nxt += 1
        ao = AO[t]
        prevc = ACFF[t - 1] if t > 0 else ACFF[t]
        pxo = np.where(np.isfinite(ao), ao, prevc)
        E = cash + float(np.nansum(sh * pxo))
        for i in list(sell_orders):
            if sh[i] <= 0:
                del sell_orders[i]
                continue
            if np.isfinite(ao[i]) and not LD[t, i]:
                v = sh[i] * ao[i]
                cash += v * (1 - sr)
                rec(t, i, "sell", v, RO[t, i], sr)
                sh[i] = 0.0
                del sell_orders[i]
            elif t >= sell_orders[i]:
                price = ACFF[t, i]
                v = sh[i] * (price if np.isfinite(price) else 0.0)
                cash += v * (1 - sr)
                rec(t, i, "forced_sell", v, RC[t, i] if np.isfinite(RC[t, i]) else float("nan"), sr)
                sh[i] = 0.0
                del sell_orders[i]
        buys = []
        for i, exp in list(buy_orders.items()):
            if t > exp:
                expired.append({"date": cal[t], "code": codes[i], "reason": "deferred_too_long"})
                del buy_orders[i]
                continue
            if not np.isfinite(ao[i]):
                continue
            held = sh[i] * ao[i]
            need = WEIGHT * E - held
            if need < 0:
                if not LD[t, i]:
                    v = -need
                    cash += v * (1 - sr)
                    sh[i] -= v / ao[i]
                    rec(t, i, "trim", v, RO[t, i], sr)
                    del buy_orders[i]
                continue
            if LU[t, i]:
                continue
            buys.append((i, need))
        if buys:
            tot = sum(v * (1 + br) for _, v in buys)
            f = min(1.0, cash / tot) if tot > 0 else 1.0
            for i, v in buys:
                v = v * f
                if v <= 0:
                    continue
                sh[i] += v / ao[i]
                cash -= v * (1 + br)
                rec(t, i, "buy", v, RO[t, i], br)
                del buy_orders[i]
        acf = ACFF[t]
        eq[t] = cash + float(np.sum(sh[sh > 0] * np.nan_to_num(acf[sh > 0])))
    held = {codes[i]: float(sh[i]) for i in np.flatnonzero(sh > 0)}
    return {"t0": t0, "dates": cal[t0:], "eq": eq[t0:] / capital, "fills": fills, "expired": expired,
            "held": held, "pending_buys": [codes[i] for i in buy_orders], "pending_sells": [codes[i] for i in sell_orders]}


def bench_nav(adj50: pd.Series, t0: int, br: float) -> np.ndarray:
    v = adj50.values.astype(float)
    return v[t0:] / v[t0 - 1] * (1 - br)


def month_end_events(dates, eq, bench, now_date, ts):
    out = []
    ser = pd.DataFrame({"eq": eq, "bench": bench}, index=pd.DatetimeIndex(dates))
    for per, g in ser.groupby(ser.index.to_period("M")):
        if per.end_time.normalize() >= now_date:
            continue
        d = g.index[-1]
        out.append({"type": "nav", "key": f"nav|{per}", "ts": ts, "month": str(per), "date": str(d.date()),
                    "nav": round(float(g["eq"].iloc[-1]), 6), "bench_nav_0050_adj": round(float(g["bench"].iloc[-1]), 6)})
    return out


# ───────────────────────── 紀錄檔（append-only、冪等）─────────────────────────
def _js(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (pd.Timestamp, pd.Period)):
        return str(o.date()) if isinstance(o, pd.Timestamp) else str(o)
    raise TypeError(type(o))


def load_log(path: Path):
    ev, bad = [], 0
    if not Path(path).exists():
        return ev, bad
    with open(path, "rb") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                ev.append(json.loads(raw.decode("utf-8")))
            except Exception:  # noqa: BLE001  壞行只計數，不改寫檔案
                bad += 1
    return ev, bad


def append_events(path: Path, events, keys: set):
    new, seen = [], set(keys)
    for e in events:
        if e["key"] not in seen:
            seen.add(e["key"])
            new.append(e)
    if not new:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    pre = b""
    if path.exists() and path.stat().st_size:
        with open(path, "rb") as f:
            f.seek(-1, os.SEEK_END)
            if f.read(1) != b"\n":
                pre = b"\n"
    body = pre + "".join(json.dumps(e, ensure_ascii=False, default=_js) + "\n" for e in new).encode("utf-8")
    with open(path, "ab") as f:
        f.write(body)
    keys.update(e["key"] for e in new)
    return len(new)


# ───────────────────────── 資料來源 ─────────────────────────
def ds_settled(df, mtime, period: pd.Period, D: pd.Timestamp) -> bool:
    """該科目已「塵埃落定」：快取已含目標季，或快取是在法定期限日隔天零時之後才抓的（缺就是真的缺，不補猜）。"""
    if df is not None and len(df) and "date" in df.columns:
        if (pd.PeriodIndex(pd.to_datetime(df["date"]), freq="Q") == period).any():
            return True
    cutoff = (D + pd.Timedelta(days=1)).tz_localize(TZ).timestamp()
    return mtime is not None and mtime >= cutoff


def adjust_bars(raw, div, spl, cr, pv):
    """FinMind 原始日線＋事件表 → bars。Open/High/Low/Close 為原始價；Adj Close＝原始收盤×累計還原因子。
    還原事件（股利／分割／減資／面額變更）由 adjust._combine_adjustment_events 合併，累乘方式與
    precheck_supply_tightness.adjusted_close（回測所用）逐行相同。無有效價格回傳 None。"""
    if raw is None or len(raw) == 0 or "date" not in raw.columns:
        return None
    r = raw.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)
    dates = r["date"].astype(str).tolist()
    close = dict(zip(dates, pd.to_numeric(r["close"], errors="coerce").astype(float)))
    div, spl, cr, pv = (x if x is not None else pd.DataFrame() for x in (div, spl, cr, pv))
    fac = np.ones(len(r))
    if not (div.empty and spl.empty and cr.empty and pv.empty):
        ev = adj._combine_adjustment_events(div, spl, cr, pv, close, dates)
        if len(ev):
            d_arr = np.array(dates)
            for _, e in ev.sort_values("ex_date", ascending=False).iterrows():
                fac[d_arr < str(e["ex_date"])] *= float(e["factor"])
    num = lambda k: pd.to_numeric(r[k], errors="coerce").astype(float).values  # noqa: E731
    c = num("close")
    out = pd.DataFrame({"Open": num("open"), "High": num("max"), "Low": num("min"), "Close": c, "Adj Close": c * fac},
                       index=pd.DatetimeIndex(pd.to_datetime(dates)))
    out = out[out["Close"] > 0]
    for k in ("Open", "High", "Low"):
        out.loc[~(out[k] > 0), k] = np.nan
    return out if len(out) else None


def px_ready(df, mtime, need_date: pd.Timestamp, is_price: bool) -> bool:
    """價格類資料已「塵埃落定」：快取已含 need_date 當日，或快取是在 need_date 隔天零時之後才抓的（缺就是真的缺，不補猜）。"""
    if is_price and df is not None and len(df) and "date" in df.columns and str(df["date"].max()) >= str(need_date.date()):
        return True
    return mtime is not None and mtime >= (need_date + pd.Timedelta(days=1)).tz_localize(TZ).timestamp()


class LiveSource:
    # 先.十-二（2026-10-02）：read_only=True 時完全不呼叫 FinMind，只讀快取；唯一抓取者是 research/finmind_warmup.py。
    def __init__(self, read_only=False):
        import finmind_client as fc
        self.fc = fc
        self.read_only = read_only
        self.fallback: set = set()
        self.calendar_source = "finmind"
        self._ph = None

    def _cache(self, ds, code, start=PRICE_START):
        p = self.fc._cache_path(ds, code, start, None)
        if not p.exists():
            return None, None
        try:
            return pd.read_parquet(p), p.stat().st_mtime
        except Exception:  # noqa: BLE001
            return None, None

    def _fresh(self, ds, code, hours):
        df, mt = self._cache(ds, code)
        return mt is not None and (time.time() - mt) < hours * 3600

    # 交易日曆＝0050 的完整日線（FinMind 原始價＋事件還原，與回測同源）；今天盤中（14:30 前）的 bar 一律捨棄。
    # FinMind 失敗才退 yfinance 並標記 calendar_source=fallback。
    def calendar(self, now):
        try:
            d = self._calendar_finmind(now)
            self.calendar_source = "finmind"
        except Exception as e:  # noqa: BLE001
            print(f"[警告] 0050 日曆 FinMind 來源失敗，改用 yfinance 備援：{type(e).__name__}: {e}", flush=True)
            d = _yf_one("0050.TW", "6y")
            d = d[d["Close"] > 0]
            self.calendar_source = "fallback"
        if len(d) and d.index[-1].date() == now.date() and (now.hour, now.minute) < CLOSE_HHMM:
            d = d.iloc[:-1]
        return d["Adj Close"].astype(float)

    def _calendar_finmind(self, now):
        if not self.read_only:
            self.refresh_events(max_age_hours=20)
            for ds, hrs in zip(PRICE_DS, (3, 20, 20)):
                if not self._fresh(ds, "0050", hrs):
                    self.fc._fetch(ds, "0050", PRICE_START, None, force_refresh=True)
        d = self._bars_from_cache("0050")
        if d is None or len(d) < 100:
            raise RuntimeError("FinMind 0050 日線不足")
        return d

    def _events_all(self):
        out = {}
        for ds in EVENT_DS_ALL:
            df, _ = self._cache(ds, "")
            out[ds] = df
        return out

    def _bars_from_cache(self, code, ev=None):
        raw, _ = self._cache(PRICE_DS[0], code)
        if raw is None or raw.empty:
            return None
        ev = ev if ev is not None else self._events_all()
        div, _ = self._cache(PRICE_DS[1], code)
        cr, _ = self._cache(PRICE_DS[2], code)
        spl, pv = ev.get(EVENT_DS_ALL[0]), ev.get(EVENT_DS_ALL[1])
        pick = lambda f: f[f["stock_id"].astype(str) == code] if f is not None and len(f) and "stock_id" in f.columns else None  # noqa: E731
        return adjust_bars(raw, div, pick(spl), cr, pick(pv))

    def events_ready(self, need_date):
        for ds in EVENT_DS_ALL:
            df, mt = self._cache(ds, "")
            if mt is None or not px_ready(df, mt, need_date, False):
                return False
        return True

    def refresh_events(self, max_age_hours=0):
        """全市場事件表（分割／面額變更；其餘兩個還原資料集在註冊層級不接受全市場查詢，只能逐檔）。"""
        if self.read_only:
            return
        for ds in EVENT_DS_ALL:
            if max_age_hours and self._fresh(ds, "", max_age_hours):
                continue
            self.fc._fetch(ds, "", PRICE_START, None, force_refresh=True)

    def px_pending(self, code, need_date):
        miss = []
        for k, ds in enumerate(PRICE_DS):
            df, mt = self._cache(ds, code)
            if not px_ready(df, mt, need_date, k == 0):
                miss.append(ds)
        return miss

    def refresh_px(self, code, which):
        if self.read_only:
            return
        for ds in which:
            self.fc._fetch(ds, code, PRICE_START, None, force_refresh=True)

    def ensure_px(self, codes, last_bar):
        """持股的價格快取補到最新一根 bar（價格 1 次、股利／減資每日各 1 次）；封鎖即停，失敗留給下一輪。"""
        n = 0
        if self.read_only:
            return n
        for c in codes:
            df, _ = self._cache(PRICE_DS[0], c)
            need = [PRICE_DS[0]] if df is None or df.empty or str(df["date"].max()) < str(last_bar.date()) else []
            need += [ds for ds in PRICE_DS[1:] if not self._fresh(ds, c, 20)]
            for ds in need:
                try:
                    self.fc._fetch(ds, c, PRICE_START, None, force_refresh=True)
                    n += 1
                except Exception as e:  # noqa: BLE001
                    print(f"[警告] 持股 {c} {ds} 更新失敗：{e}", flush=True)
                    if "封鎖" in str(e):
                        return n
        return n

    def official_open(self, code, date):
        """官方 TWSE/TPEx 原始開盤價（data/price_history.json，約最近 90 個交易日）；查不到回 None。"""
        if self._ph is None:
            try:
                self._ph = json.loads(PRICE_HISTORY_PATH.read_text(encoding="utf-8")).get("prices", {})
            except Exception:  # noqa: BLE001
                self._ph = {}
        for row in self._ph.get(code, []):
            if row.get("date") == str(date.date()):
                o = row.get("open")
                return float(o) if o else None
        return None

    def universe(self):
        fc = self.fc
        path = fc._cache_path("TaiwanStockInfo", "", "2000-01-01", None)
        if not self.read_only and path.exists() and (time.time() - path.stat().st_mtime) > 45 * 86400:
            try:
                fc._fetch("TaiwanStockInfo", "", "2000-01-01", None, force_refresh=True)
            except Exception:  # noqa: BLE001  更新失敗沿用舊名冊（降級），不中斷
                pass
        info = pd.read_parquet(path).drop_duplicates("stock_id")
        info["stock_id"] = info["stock_id"].astype(str)
        info = info[info["stock_id"].str.fullmatch(r"\d{4}") & info["type"].isin(["twse", "tpex"])]
        ind = info["industry_category"].astype(str)
        info = info[~ind.isin(pt.FINANCIAL) & ~ind.str.contains(pt.NON_STOCK)]
        return pd.DataFrame({"code": info["stock_id"].values, "industry": info["industry_category"].astype(str).values,
                             "suffix": np.where(info["type"].values == "twse", ".TW", ".TWO")}).sort_values("code").reset_index(drop=True)

    def stmt_state(self, code):
        out = {}
        for k, ds in STMT_DS:
            p = self.fc._cache_path(ds, code, STMT_START, None)
            if p.exists():
                try:
                    out[k] = (pd.read_parquet(p), p.stat().st_mtime)
                except Exception:  # noqa: BLE001
                    out[k] = (None, None)
            else:
                out[k] = (None, None)
        return out

    def refresh_stmt(self, code, which):
        # 為什麼用 _fetch 而非 load_dev：紙.二是「即時前進訊號」，換股日當下必須取到最新財報，而 load_dev
        # 結構上封頂於 VAL_END(2024-12-31)。此處不做任何 holdout 評估或績效計算，只存快取（供換股日 PIT
        # 截斷後計分），起日 2024-01-01 與既有 2010-2024／2025-latest 快取檔名不同，不互相覆蓋。
        # 節流與封鎖保護由 _fetch 內建（共用跨行程 rate_limit_state.json）。
        if self.read_only:
            return
        ds_of = dict(STMT_DS)
        for k in which:
            self.fc._fetch(ds_of[k], code, STMT_START, None, force_refresh=True)

    def prices(self, uni_rows, start, end):
        """uni_rows: [(code, suffix)] → {code: DataFrame[Open,High,Low,Close,Adj Close]}，只回傳有資料者。
        主來源 FinMind 快取（原始價＋事件還原，與回測同源）；FinMind 無可用價格者才退 yfinance，並記入 self.fallback。"""
        self.fallback = set()
        out, need_fb = {}, []
        ev = self._events_all()
        ev_missing = any(v is None for v in ev.values())
        for c, s in uni_rows:
            d = None
            if not ev_missing:
                try:
                    d = self._bars_from_cache(c, ev)
                except Exception:  # noqa: BLE001
                    d = None
            if d is not None:
                d = d[(d.index >= start) & (d.index <= end)]
            if d is None or d.empty:
                need_fb.append((c, s))
            else:
                out[c] = d
        if need_fb:
            got = self._yf_prices(need_fb, start, end)
            self.fallback = set(got)
            out.update(got)
        return out

    def _yf_prices(self, uni_rows, start, end):
        out = {}
        todo = list(uni_rows)
        for attempt in range(2):
            miss = []
            for i in range(0, len(todo), 100):
                chunk = todo[i:i + 100]
                tk = [c + s for c, s in chunk]
                try:
                    import yfinance as yf
                    raw = yf.download(tk, start=str(start.date()), end=str((end + pd.Timedelta(days=1)).date()),
                                      auto_adjust=False, group_by="ticker", progress=False, threads=True)
                except Exception:  # noqa: BLE001
                    miss += chunk
                    continue
                for (c, s), t in zip(chunk, tk):
                    d = _pick(raw, t, len(tk) == 1)
                    if d is None:
                        miss.append((c, s))
                    else:
                        out[c] = d[d.index <= end]
            todo = [(c, ".TWO" if s == ".TW" else ".TW") for c, s in miss]
            if not todo:
                break
        return out


def _flat(d):
    if isinstance(d.columns, pd.MultiIndex):
        d = d.copy()
        d.columns = d.columns.get_level_values(0)
    return d


def _clean(d):
    need = ["Open", "High", "Low", "Close", "Adj Close"]
    if d is None or d.empty or any(c not in d.columns for c in need):
        return None
    d = d[need].dropna(subset=["Close", "Adj Close"])
    d.index = pd.DatetimeIndex(pd.to_datetime(d.index)).tz_localize(None).normalize()
    d = d[~d.index.duplicated(keep="last")].sort_index()
    return d if len(d) else None


def _pick(raw, ticker, single):
    try:
        d = _flat(raw) if single else raw[ticker]
    except Exception:  # noqa: BLE001
        return None
    return _clean(d)


def _yf_one(ticker, period):
    import yfinance as yf
    d = _clean(_flat(yf.download(ticker, period=period, auto_adjust=False, progress=False)))
    if d is None:
        raise RuntimeError(f"yfinance 無 {ticker} 資料")
    return d


# ───────────────────────── 主流程 ─────────────────────────
def run(src, now, log_path=LOG_PATH, state_path=STATE_PATH, budget=REFRESH_BUDGET, dry=False, verbose=True):
    log = (lambda *a: print(*a, flush=True)) if verbose else (lambda *a: None)
    ts = now.isoformat(timespec="seconds")
    now_date = pd.Timestamp(now.year, now.month, now.day)
    ev, bad = load_log(log_path)
    keys = {e.get("key") for e in ev}
    new: list[dict] = []
    res = {"status": None, "new_events": 0}

    def warn(reason, detail=""):
        res["degraded"] = True
        new.append({"type": "warning", "key": f"warn|{now_date.date()}|{reason}", "ts": ts, "reason": reason,
                    "detail": str(detail)[:300]})
        log(f"[警告] {reason} {detail}")

    def flush():
        res["new_events"] = 0 if dry else append_events(log_path, new, keys)

    if bad:
        warn("log_bad_lines", f"{bad} 行無法解析（不改寫原檔）")
    first_window = deadline(FIRST_PERIOD) - pd.Timedelta(days=WINDOW_BEFORE_DAYS)
    if now_date < first_window:
        res["status"] = "before_window"
        log(f"尚未到首次換股視窗（{first_window.date()} 起），不動作。首次換股日 {FIRST_REBALANCE.date()}。")
        return res
    try:
        adj50 = src.calendar(now)
    except Exception as e:  # noqa: BLE001
        warn("calendar_failed", e)
        flush()
        res["status"] = "degraded"
        return res
    cal = adj50.index
    last_bar = cal[-1]
    if (now_date - last_bar).days > 10:
        warn("prices_stale", f"最新 bar {last_bar.date()}，已逾 10 日，不計算")
        flush()
        res["status"] = "degraded"
        return res
    open_periods = [p for p in periods_until(now_date + pd.Timedelta(days=WINDOW_BEFORE_DAYS))
                    if f"signal|{p}" not in keys and f"skip|{p}" not in keys
                    and now_date >= deadline(p) - pd.Timedelta(days=WINDOW_BEFORE_DAYS)]
    st = _load_state(state_path)
    if not open_periods and st.get("last_bar") == str(last_bar.date()) and not dry:
        res["status"] = "noop"
        flush()
        return res
    try:
        uni = src.universe()
    except Exception as e:  # noqa: BLE001
        warn("universe_failed", e)
        flush()
        res["status"] = "degraded"
        return res
    suffix = dict(zip(uni["code"], uni["suffix"]))
    br, sr = core.rates(1.0)
    spent = 0
    for p in open_periods:
        D = deadline(p)
        R = rebalance_day(cal, D)
        if now_date <= D:
            continue
        flags = {c: _settled(src, c, p, D) for c in uni["code"]}
        todo = [c for c, (ok, _) in flags.items() if not ok]
        used, touched = _refresh(src, todo, flags, budget - spent, warn)
        spent += used
        for c in touched:
            flags[c] = _settled(src, c, p, D)
        n_set = sum(ok for ok, _ in flags.values())
        frac = n_set / max(1, len(flags))
        res[f"settled_{p}"] = round(frac, 4)
        log(f"{p}：財報塵埃落定 {n_set}/{len(flags)}（{frac:.1%}），本輪 FinMind 呼叫 {spent} 次；換股日 {R.date() if R is not None else '未到'}")
        if R is None:
            continue
        late = int((cal > R).sum())
        need = cal[cal <= D][-1]
        used, px_frac, ev_ok = _px_phase(src, list(uni["code"]), need, budget - spent, warn)
        spent += used
        res[f"px_ready_{p}"] = round(px_frac, 4)
        log(f"{p}：價格／還原事件就緒 {px_frac:.1%}（事件表{'已更新' if ev_ok else '未更新'}），本輪 FinMind 累計呼叫 {spent} 次")
        full = frac >= SETTLED_MIN and px_frac >= SETTLED_MIN and ev_ok
        if not full:
            if late <= MAX_LATE:
                continue
            if frac < PRICE_COV_MIN:
                new.append({"type": "skipped_data_unready", "key": f"skip|{p}", "ts": ts, "period": str(p), "R": str(R.date()),
                            "reason": f"換股日後逾 {MAX_LATE} 個交易日，財報覆蓋率 {frac:.1%} < {PRICE_COV_MIN:.0%}（財報），沿用既有持股，不補算",
                            "stmt_coverage": round(frac, 4), "n_settled": n_set, "px_ready": round(px_frac, 4)})
                continue
        if not ev_ok:
            warn("events_stale", f"{p}：全市場還原事件表（分割／面額變更）未能更新，沿用舊快取或備援")
        tables = {}
        for c in uni["code"]:
            if frac < SETTLED_MIN and not flags[c][0]:
                tables[c] = None  # 未入庫者當季不計分
                continue
            s = src.stmt_state(c)
            tables[c] = quarter_table_from_frames(s["fs"][0], s["bs"][0], s["cf"][0])
        start = R - pd.DateOffset(months=15)
        bars = src.prices([(c, suffix[c]) for c in uni["code"]], start, last_bar)
        fb = sorted(getattr(src, "fallback", set()) & set(bars))
        cov = len(bars) / max(1, len(uni))
        if cov < PRICE_COV_MIN:
            if late > MAX_LATE:
                new.append({"type": "skipped_data_unready", "key": f"skip|{p}", "ts": ts, "period": str(p), "R": str(R.date()),
                            "reason": f"換股日後逾 {MAX_LATE} 個交易日，價格覆蓋率 {cov:.1%} < {PRICE_COV_MIN:.0%}（價格），沿用既有持股，不補算",
                            "stmt_coverage": round(frac, 4), "price_coverage": round(cov, 4)})
            else:
                warn("price_coverage_low", f"{p}：價格覆蓋 {cov:.1%} < {PRICE_COV_MIN:.0%}，不產生訊號")
            continue
        if fb:
            warn("price_fallback", f"{p}：{len(fb)} 檔 FinMind 無可用價格，改用 yfinance 備援（price_source=fallback）")
        prev = [e for e in ev + new if e.get("type") == "signal"]
        prev_codes = [x["code"] for x in prev[-1]["picks"]] if prev else []
        sig = build_signal(R, target_period(R), uni, tables, bars, prev_codes)
        after = max(R, last_bar)
        new.append({"type": "signal", "key": f"signal|{p}", "ts": ts, "period": str(p), "R": str(R.date()),
                    "target_quarter": str(target_period(R)), "after_date": str(after.date()),
                    "fill_rule": "after_date 後第一個交易日開盤", "n_settled": n_set, "n_unsettled": len(flags) - n_set,
                    "stmt_mode": "full" if frac >= SETTLED_MIN else "partial", "stmt_coverage": round(frac, 4),
                    "px_ready": round(px_frac, 4), "price_coverage": round(cov, 4),
                    "price_source": "FinMind TaiwanStockPrice 原始價＋adjust.py 事件還原（股利/分割/減資/面額變更）"
                                    + (f"；{len(fb)} 檔備援 yfinance" if fb else ""),
                    "price_fallback_codes": fb[:200], "universe_info": "TaiwanStockInfo 快取",
                    "universe_n": len(uni), **sig})
        log(f"{p}：已產生訊號 {len(sig['picks'])} 檔（存活 {sig['n_alive']}、可計分 {sig['n_scored']}、落後池 {sig['n_pool']}）")
    sigs = [e for e in ev + new if e.get("type") == "signal"]
    if sigs:
        _sim_phase(src, sigs, suffix, cal, adj50, now, now_date, ts, br, sr, ev, new, warn, res)
    flush()
    if not dry:
        if not res.get("degraded"):
            _save_state(state_path, {"last_bar": str(last_bar.date()), "ts": ts})
    res["status"] = "ok"
    return res


def _refresh(src, todo, flags, budget, warn):
    """逐檔補抓尚未塵埃落定的財報科目；遇封鎖或連續 5 次失敗即停（降級，不補猜）。回傳 (呼叫數, 動過的代號)。"""
    used, fails, touched = 0, 0, []
    for c in todo:
        for k in flags[c][1]:
            if used >= budget or fails >= 5:
                return used, touched
            used += 1
            try:
                src.refresh_stmt(c, [k])
                fails = 0
                if c not in touched:
                    touched.append(c)
            except Exception as e:  # noqa: BLE001
                fails += 1
                warn("refresh_failed", f"{c}/{k}: {e}")
                if "封鎖" in str(e):
                    return used, touched
    return used, touched


def _px_phase(src, codes, need, budget, warn):
    """價格／還原事件補抓（與財報共用每輪預算）：全市場事件表 2 次，其餘逐檔；遇封鎖或連續 5 次失敗即停。
    回傳 (呼叫數, 價格就緒比例, 事件表是否新鮮)。"""
    used, fails = 0, 0
    try:
        if not src.events_ready(need) and budget >= 2:
            src.refresh_events()
            used += 2
    except Exception as e:  # noqa: BLE001
        warn("events_failed", e)
        fails += 5 if "封鎖" in str(e) else 0
    pend = {c: m for c in codes if (m := src.px_pending(c, need))}
    stop = fails >= 5
    for c, miss in pend.items():
        if stop:
            break
        for ds in miss:
            if used >= budget or fails >= 5:
                stop = True
                break
            used += 1
            try:
                src.refresh_px(c, [ds])
                fails = 0
            except Exception as e:  # noqa: BLE001
                fails += 1
                warn("px_refresh_failed", f"{c}/{ds}: {e}")
                if "封鎖" in str(e):
                    stop = True
                    break
    left = sum(1 for c in codes if src.px_pending(c, need))
    return used, 1 - left / max(1, len(codes)), bool(src.events_ready(need))


def _settled(src, code, period, D):
    s = src.stmt_state(code)
    miss = [k for k, (df, mt) in s.items() if not ds_settled(df, mt, period, D)]
    return (not miss, miss)


def _sim_phase(src, sigs, suffix, cal, adj50, now, now_date, ts, br, sr, ev, new, warn, res):
    codes = sorted({x["code"] for s in sigs for x in s["picks"]})
    start = min(pd.Timestamp(s["after_date"]) for s in sigs) - pd.Timedelta(days=60)
    try:
        src.ensure_px(codes, cal[-1])
    except Exception as e:  # noqa: BLE001  持股價格快取補抓失敗只降級，沿用現有快取
        warn("px_ensure_failed", e)
    try:
        bars = src.prices([(c, suffix.get(c, ".TW")) for c in codes], start, cal[-1])
    except Exception as e:  # noqa: BLE001
        warn("price_fetch_failed", e)
        return
    fb = getattr(src, "fallback", set())
    for c in codes:
        if c not in bars:
            warn("no_bars", f"持股 {c} 取不到價格，不補猜（無法成交／估值該檔）")
    if fb:
        warn("price_fallback_holdings", f"持股 {sorted(fb)} 價格改用 yfinance 備援（price_source=fallback）")
    no_ref = []
    sg = [{"period": s["period"], "after": pd.Timestamp(s["after_date"]), "picks": [x["code"] for x in s["picks"]]}
          for s in sigs]
    r = simulate(sg, cal, bars, br, sr)
    if r is None:
        res["sim"] = "尚無已啟動訊號"
        return
    logged = {e["key"]: e for e in ev if e.get("type") == "fill"}
    for f in r["fills"]:
        key = f"fill|{f['date'].date()}|{f['code']}|{f['side']}"
        e = {"type": "fill", "key": key, "ts": ts, "date": str(f["date"].date()), "code": f["code"], "side": f["side"],
             "signal_period": f["period"], "value": round(f["value"], 2), "px_raw": round(f["px_raw"], 4),
             "shares_raw": round(f["value"] / f["px_raw"], 4) if f["px_raw"] and np.isfinite(f["px_raw"]) else None,
             "cost": round(f["cost"], 2), "px_basis": "adj_close_forced(原始收盤供對照)" if f["side"] == "forced_sell" else "raw_open",
             "price_source": "fallback" if f["code"] in fb else "finmind+adjust"}
        if key in logged:
            old = logged[key]
            if abs(old["px_raw"] - e["px_raw"]) > 0.005 * abs(old["px_raw"]) or abs(old["value"] - e["value"]) > 0.02 * abs(old["value"]):
                warn(f"replay_mismatch|{key}", f"已記 value={old['value']} px={old['px_raw']}，重算 value={e['value']} px={e['px_raw']}（以已記錄為準）")
        else:
            new.append(e)
            if f["side"] != "forced_sell":
                ref = src.official_open(f["code"], f["date"])
                if ref is None or not ref > 0:
                    no_ref.append(f"{f['code']}@{f['date'].date()}")
                elif abs(f["px_raw"] - ref) / ref > XCHECK_TOL:
                    warn(f"open_xcheck|{f['code']}|{f['date'].date()}",
                         f"成交開盤價 {f['px_raw']:.4f} 與官方 TWSE/TPEx 開盤 {ref:.4f} 差 {abs(f['px_raw'] - ref) / ref:.2%} > {XCHECK_TOL:.1%}")
    if no_ref:
        warn("open_xcheck_missing", f"{len(no_ref)} 筆成交無官方開盤價可交叉核對（price_history.json 無該日資料）：{no_ref[:10]}")
    for x in r["expired"]:
        new.append({"type": "order_expired", "key": f"expired|{x['date'].date()}|{x['code']}|{x['reason']}", "ts": ts,
                    "date": str(x["date"].date()), "code": x["code"], "reason": x["reason"]})
    bn = bench_nav(adj50, r["t0"], br)
    new.extend(month_end_events(r["dates"], r["eq"], bn, now_date, ts))
    res["sim"] = {"n_fills": len(r["fills"]), "nav": float(r["eq"][-1]), "bench": float(bn[-1]), "held": len(r["held"])}


def _load_state(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _save_state(p, d):
    try:
        Path(p).write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    except Exception:  # noqa: BLE001  狀態檔只是加速用，寫不進去不影響結果
        pass


# ───────────────────────── 判讀（滿 4 季才輸出績效）─────────────────────────
def report(src, now, log_path=LOG_PATH):
    ev, _ = load_log(log_path)
    sigs = [e for e in ev if e.get("type") == "signal"]
    print(NOTICE)
    print(f"已記錄換股 {len(sigs)} 次、成交 {sum(e.get('type') == 'fill' for e in ev)} 筆、"
          f"月末淨值 {sum(e.get('type') == 'nav' for e in ev)} 筆。")
    if pd.Timestamp(now.date()) < FIRST_INTERPRET:
        print(f"尚未滿 4 季：首次判讀日 {FIRST_INTERPRET.date()}，此前不輸出任何績效數字（避免偷看）。")
        return None
    adj50 = src.calendar(now)
    uni = src.universe()
    suffix = dict(zip(uni["code"], uni["suffix"]))
    br, sr = core.rates(1.0)
    codes = sorted({x["code"] for s in sigs for x in s["picks"]})
    start = min(pd.Timestamp(s["after_date"]) for s in sigs) - pd.Timedelta(days=60)
    bars = src.prices([(c, suffix.get(c, ".TW")) for c in codes], start, adj50.index[-1])
    sg = [{"period": s["period"], "after": pd.Timestamp(s["after_date"]), "picks": [x["code"] for x in s["picks"]]} for s in sigs]
    r = simulate(sg, adj50.index, bars, br, sr)
    if r is None:
        print("尚無已啟動持股。")
        return None
    rs = core.eq_to_ret(r["eq"])
    rb = core.eq_to_ret(bench_nav(adj50, r["t0"], br))
    out = {"sortino": core.sortino(rs), "sortino_0050": core.sortino(rb), "mdd": core.mdd(rs), "mdd_0050": core.mdd(rb)}
    out["pass_sortino"] = bool(out["sortino"] >= out["sortino_0050"])
    out["pass_mdd"] = bool(out["mdd"] > -0.50)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    now = datetime.now(TZ)
    if "--status" in argv:
        ev, bad = load_log(LOG_PATH)
        from collections import Counter
        print(dict(Counter(e.get("type") for e in ev)), f"壞行 {bad}", NOTICE)
        return 0
    try:
        src = LiveSource(read_only=True)
        if "--report" in argv:
            report(src, now)
            return 0
        LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
        except FileExistsError:
            if time.time() - LOCK_PATH.stat().st_mtime < 3 * 3600:
                print("另一個紙.二行程執行中，略過。")
                return 0
            LOCK_PATH.touch()
        try:
            run(src, now, budget=0, dry="--dry" in argv)
        finally:
            try:
                LOCK_PATH.unlink()
            except OSError:
                pass
    except Exception as e:  # noqa: BLE001  守門員／主流程自身失敗只降級，不得拖垮排程（CLAUDE.md 十二）
        print(f"[降級] 紙.二執行失敗：{type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
