# -*- coding: utf-8 -*-
"""先.一三三-1（2026-10-23，DevQueue）：V1 等權再平衡溢酬——台股 2007-07～2014 時點宇宙單發（事前登記 #462）。

規則照 `docs/PREREG_VAR1018_V1_equal_weight_rebalance_tw2007_FINAL.md`「定稿條文」（commit 7e657456b6），不改任何一條：
- t0＝2007-07-02，驗證期 2007-07-02～2014-12-31；宇宙＝t0 前後 10 天內有價格列的上市＋上櫃普通股（4 碼、非 0 開頭，含之後下市）。
- 策略：t0 收盤等權買入，之後每 21 個交易日（t0 起算）把仍在市的股票拉回等權；基準：同一組股票 t0 等權後不再平衡。
- 下市股：最後交易日收盤出場、持現金；停牌期間持有不動、無價格日不計報酬。
- 缺資料的下市股（最後可得價到下市日 >20 天，同涵蓋率定義的 tail 門檻）：悲觀＝之後報酬 −100%；中性＝最後可得收盤出場。兩者都過才 PASS，N 只 +1。
- 價格＝FinMind 原始收盤（2006 起本機快取）∪ 官方日檔（v1_official_daily，與涵蓋率計算同一批日期）；還原一律用
  `adjust.adjustment_events()`（含官方減資補充事件），factor 套法與 `adjust._finmind_adjusted_frame()` 相同（日期 < ex_date 的價格乘 factor）。
- 成本 `validation.costs.round_trip_cost_pct()` 1×（另報 2×／3×），依實際換手逐腿收：買腿＝手續費＋滑價，賣腿＝其餘（含證交稅）。
- 判準依序：天條一（策略與基準：全期、2007-10-30～2008-11-21、2011-05-02～2011-12-19 回撤任一 >50% → VIOLATES_SURVIVAL）→
  ①全期溢酬（扣 1×）>0 →②隨機一半母體（種子 20261018＋i，N＝100）溢酬>0 比例 ≥95% →③8 期（2007H2＋2008～2014）≥7 期為正 →
  ④3× 成本全期溢酬>0 →⑤第 8 關：策略扣 1× 年化報酬 > 同期 0050 含息年化報酬。

[自行裁量]（寫在結果檔 discretion 欄，總司令／Cowork 可推翻）：
1. 「溢酬」＝策略年化報酬 − 基準年化報酬（逐期用期間報酬差）；正負號與總報酬差相同。
2. 再平衡日停牌（當天沒有成交價）的股票不能交易：維持原部位，其餘資金在有價股票間等分。
3. t0 當天沒有成交但 t0+10 天內有的股票：以第一個有價日收盤買入（之前視同持現金、不計報酬）——等價於「在 t0 母體、晚幾天才買到」。
4. 非下市股但價格在 2014-12-31 前 >20 天就斷了（例如資料源缺漏）：兩種假設都以最後可得收盤出場，件數名單揭露。
5. `adjust.adjustment_events()` 內部的 `load_dev()` 在本程式裡改指向本機既有快取（2006～2014 價格、2006 起股利、2010 起減資等），
   **不發任何網路請求**；每檔用到哪個快取檔、哪些資料集沒有快取，揭露在結果檔。2014-12-31 以後的事件只把更早的價格乘同一個常數，
   不影響 2007～2014 的報酬，故截到 2014-12-31 不改變結果。不修改 adjust.py 原始碼（十三節）。
6. 第 8 關用 PREREG 定稿條文的寫法（0050 含息年化、同期）；`validation.passive_benchmark_gate.evaluate_gate8()` 的被動基準結果表
   只有 2015～2024 train／val 兩期，對 2007～2014 不適用，不呼叫。

用法：
  python research/var1018_v1_oneshot.py selftest   # 合成資料自測＋無網路守門，不碰真資料報酬
  python research/var1018_v1_oneshot.py probe      # 修訂 R2 後資料探測（母體／涵蓋／跳動數），不算報酬
  python research/var1018_v1_oneshot.py run        # 只跑一次；結果檔已存在就拒跑
輸出：research/data/var1018_v1_oneshot_result.json（git add -f 入庫）
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import numpy as np
import pandas as pd

import finmind_client as F

HERE = Path(__file__).resolve().parent
RESULT = HERE / "data" / "var1018_v1_oneshot_result.json"
FILL_REPORT = HERE / "data" / "v1_reduction_fill_report.json"
PREREG = "docs/PREREG_VAR1018_V1_equal_weight_rebalance_tw2007_FINAL.md"
PREREG_COMMIT = "7e657456b6"
PREREG_R2_COMMIT = "R2_PENDING"   # 修訂 R2（先.一三三-1b）commit，單發前填入
T0, END = pd.Timestamp("2007-07-02"), pd.Timestamp("2014-12-31")
REBAL = 21
TAIL_DAYS = 20          # 同涵蓋率定義：最後一筆價格距離終點 ≤20 天才算有到終點
SEED0, N_RANDOM = 20261018, 100
SURV_LIMIT = -0.50
BEARS = {"2007-10-30～2008-11-21": ("2007-10-30", "2008-11-21"), "2011-05-02～2011-12-19": ("2011-05-02", "2011-12-19")}
PERIODS = [("2007H2", "2007-07-02", "2007-12-31")] + [(str(y), f"{y}-01-01", f"{y}-12-31") for y in range(2008, 2015)]
CUTOFF = "2014-12-31"


# ------------------------------------------------------------------ 無網路守門＋adjust 快取轉接
class NoNetwork(RuntimeError):
    pass


def install_no_network_guard() -> None:
    """finmind_client._fetch 只准命中既有快取；快取不存在直接 raise（不發請求）。"""
    orig = F._fetch

    def guarded(dataset, data_id="", start_date="2000-01-01", end_date=None, force_refresh=False, **kw):
        if force_refresh or not F._cache_path(dataset, data_id, start_date, end_date).exists():
            raise NoNetwork(f"V1 單發禁止網路請求：{dataset} {data_id} {start_date}～{end_date} 無本機快取")
        return orig(dataset, data_id, start_date, end_date, force_refresh=False, **kw)

    F._fetch = guarded


CACHE_USE: dict[str, dict] = {}


_NAME_INDEX: dict | None = None
_DF_CACHE: dict = {}


def _pick_cache(dataset: str, data_id: str) -> Path | None:
    """挑一個「迄日 ≥2014-12-31、且不是 latest（避免把 holdout 讀進記憶體）」的快取，起日越早越好。
    快取目錄有 4 萬多個檔：檔名索引只建一次（每檔 glob 一次會讓 1,250 檔要跑十幾分鐘）。"""
    global _NAME_INDEX
    if _NAME_INDEX is None:
        _NAME_INDEX = {}
        pat = re.compile(r"^(.+?)__(.+?)__(\d{4}-\d{2}-\d{2})__(\d{4}-\d{2}-\d{2})\.parquet$")
        for name in os.listdir(F.DATA_DIR):
            m = pat.match(name)
            if m and CUTOFF <= m.group(4) <= "2024-12-31":
                _NAME_INDEX.setdefault((m.group(1), m.group(2)), []).append((m.group(3), name))
    cands = sorted(_NAME_INDEX.get((dataset, data_id or "ALL"), []))
    return F.DATA_DIR / cands[0][1] if cands else None


def local_load_dev(dataset, data_id="", start_date="2000-01-01", end_date=None, date_col="date", force_refresh=False):
    p = _pick_cache(dataset, data_id)
    CACHE_USE.setdefault(data_id or "ALL", {})[dataset] = p.name.split("__", 2)[2] if p else None
    if p is None:
        return pd.DataFrame()
    if not data_id:  # 市場全表（例如面額變更）每檔都會讀一次，只讀一次留在記憶體
        df = _DF_CACHE.get(p) if p in _DF_CACHE else _DF_CACHE.setdefault(p, pd.read_parquet(p))
    else:
        df = pd.read_parquet(p)
    if df.empty or date_col not in df.columns:
        return df
    return df[(df[date_col] >= str(start_date)) & (df[date_col] <= CUTOFF)].reset_index(drop=True)


def events_for(code: str) -> tuple[pd.DataFrame, str | None]:
    import adjust as A
    A.load_dev = local_load_dev  # 只換資料讀取來源（本機快取），adjustment_events() 邏輯不動
    try:
        return A.adjustment_events(code, "2006-01-01"), None
    except Exception as e:  # noqa: BLE001 —— 例如 FinMind 價格快取不存在但有事件：揭露，不靜默
        return A._empty_events_df(), f"{type(e).__name__}: {e}"


# ------------------------------------------------------------------ 資料
def official_closes(codes: set[str]) -> dict[str, dict]:
    """官方日檔收盤（與 var1018_v1_lowmem.build_index() 的 official 同一批日期：① 診斷缺口日＋上櫃 2007 上半年逐檔×月）。"""
    import var1018_v1_lowmem as L
    diag = {d.replace("-", "") for d in json.loads(L.DIAG.read_text(encoding="utf-8"))["weekdays_to_fill"]}
    out: dict[str, dict] = {}
    for src in ("twse", "tpex"):
        for p in sorted((L.OFF / src).glob("*.json")):
            if p.stem not in diag:
                continue
            j = json.loads(p.read_text(encoding="utf-8"))
            d = f"{p.stem[:4]}-{p.stem[4:6]}-{p.stem[6:]}"
            for code, row in (j.get("rows") or {}).items():
                if code in codes and row[3] is not None and row[3] > 0:
                    out.setdefault(code, {})[d] = float(row[3])
            del j
    for p in sorted((L.OFF / "tpex_stock").glob("*/*.json")):
        j = json.loads(p.read_text(encoding="utf-8"))
        if j.get("code") in codes:
            for day, row in (j.get("rows") or {}).items():
                if row[3] is not None and row[3] > 0:
                    out.setdefault(j["code"], {}).setdefault(str(pd.Timestamp(day).date()), float(row[3]))
    return out


def raw_close(code: str, off: dict, listed: np.ndarray | None = None, chk: np.ndarray | None = None) -> pd.Series:
    import var1018_v1_prep as V
    s = pd.Series(dtype=float)
    if V.cached("TaiwanStockPrice", code):
        d = F.load_dev("TaiwanStockPrice", code, V.FETCH_START, V.FETCH_END)
        if not d.empty:
            d = d[pd.to_numeric(d["close"], errors="coerce") > 0]
            s = pd.Series(d["close"].astype(float).values, index=d["date"].astype(str).values)
    o = pd.Series(off.get(code, {}), dtype=float)
    if len(o):
        s = pd.concat([s, o[~o.index.isin(s.index)]])  # FinMind 優先，官方補 FinMind 沒有的日子
    s = s[~s.index.duplicated()].sort_index()
    s.index = pd.to_datetime(s.index)
    if chk is not None:  # 修訂 R2①：可核對日（兩市場官方日檔皆 ok）只留官方有列的價格列（同 var1018_v1_r2_coverage.r2_filter）
        import var1018_v1_r2_coverage as R2
        kept, _ = R2.r2_filter(s.index.to_numpy().astype("datetime64[D]"), listed, chk)
        s = s[s.index.isin(pd.to_datetime(kept))]
    return s


def apply_events(s: pd.Series, ev: pd.DataFrame) -> pd.Series:
    """同 adjust._finmind_adjusted_frame()：日期 < ex_date 的價格乘 factor（由後往前累乘）。"""
    f = pd.Series(1.0, index=s.index)
    for _, e in ev.sort_values("ex_date", ascending=False).iterrows():
        f[s.index < pd.Timestamp(e["ex_date"])] *= float(e["factor"])
    return s * f


def build_data() -> dict:
    import var1018_v1_prep as V
    cands, dead = V.candidates()
    dl = pd.read_parquet(V.RAW / "TaiwanStockDelisting__ALL__1990-01-01__latest.parquet")
    dl["date"] = pd.to_datetime(dl["date"])
    ddate = dict(zip(dl["stock_id"], dl["date"]))
    del dl
    import var1018_v1_lowmem as L
    import var1018_v1_r2_coverage as R2
    codes = [c for c in cands if c != "0050"]
    off = official_closes(set(codes))
    idx = L.build_index()
    chk = R2.checkable_days(idx)
    series, meta = {}, {}
    for c in codes:
        lst = idx["listed"].get(c)
        s = raw_close(c, off, lst, chk)
        t = s.index[(s.index >= T0 - pd.Timedelta(days=10)) & (s.index <= END)]
        if len(t) == 0 or t[0] > T0 + pd.Timedelta(days=10):
            continue  # 不在 t0 母體（同 coverage_windows._code_window）
        if not R2.in_official_near(lst, T0):
            continue  # 修訂 R2②：t0 前後 10 天官方日檔沒有列＝不在母體
        ev, err = events_for(c)
        adj = apply_events(s, ev)
        series[c] = adj[(adj.index >= T0 - pd.Timedelta(days=10)) & (adj.index <= END)]
        meta[c] = {"dead": c in dead, "delist": ddate.get(c), "n_events": int(len(ev)), "events_error": err,
                   "supp_events": int((ev["event_type"] == "capital_reduction_official_supp").sum()) if len(ev) else 0}
    s50 = raw_close("0050", {})
    ev50, err50 = events_for("0050")
    a50 = apply_events(s50, ev50)
    cal = a50.index[(a50.index >= T0) & (a50.index <= END)]
    return {"series": series, "meta": meta, "cal": cal, "a50": a50, "err50": err50, "n_ev50": int(len(ev50)),
            "n_candidates": len(codes), "n_dead_candidates": len(dead)}


# ------------------------------------------------------------------ 引擎
def make_matrix(series: dict, cal: pd.DatetimeIndex, codes: list[str], meta: dict) -> dict:
    """P：交易日×股票的還原收盤（沒成交＝NaN）；以及每檔的出場日索引與「缺資料下市股」旗標。"""
    n, D = len(codes), len(cal)
    P = np.full((D, n), np.nan)
    first_px = np.full(n, np.nan)
    last_i = np.zeros(n, dtype=int)
    exit_i = np.full(n, -1)
    missing_dead = np.zeros(n, dtype=bool)
    early_alive = np.zeros(n, dtype=bool)
    for j, c in enumerate(codes):
        s = series[c]
        pre = s[s.index <= T0]
        first_px[j] = pre.iloc[-1] if len(pre) else s.iloc[0]   # [自行裁量]3：t0 前最後收盤（10 天內）或 t0 後首個收盤
        on = s.reindex(cal)
        P[:, j] = on.to_numpy()
        valid = np.where(~np.isnan(P[:, j]))[0]
        li = valid[-1] if len(valid) else 0
        last_i[j] = li
        last_date = cal[li]
        m = meta[c]
        end_j = min(m["delist"], END) if (m["dead"] and m["delist"] is not None) else END
        if m["dead"] and m["delist"] is not None and m["delist"] <= END:
            exit_i[j] = li
            missing_dead[j] = (end_j - last_date).days > TAIL_DAYS
        elif (END - last_date).days > TAIL_DAYS:
            exit_i[j] = li
            early_alive[j] = True
    # 停牌日沿用前一收盤（不計報酬）；t0 前沒成交的用第一筆價格回填（[自行裁量]3）
    Pf = pd.DataFrame(P).ffill().to_numpy()
    Pf = np.where(np.isnan(Pf), first_px[None, :], Pf)
    R = np.zeros_like(Pf)
    R[1:] = Pf[1:] / Pf[:-1] - 1.0
    R[0] = Pf[0] / first_px - 1.0  # t0 當天相對於買入價（t0 前收盤）的報酬；t0 有成交者為 0
    has_px = ~np.isnan(P)
    return {"R": R, "has_px": has_px, "exit_i": exit_i, "missing_dead": missing_dead, "early_alive": early_alive,
            "codes": codes, "last_i": last_i}


def simulate(M: dict, sel: np.ndarray, rebalance: bool, hyp: str, buy_c: float, sell_c: float) -> tuple[np.ndarray, float]:
    """回傳 (每日淨值, 累計換手)。sel：布林遮罩，選用哪些股票。hyp∈{pessimistic, neutral}。"""
    R, has_px, exit_i, md = M["R"][:, sel], M["has_px"][:, sel], M["exit_i"][sel], M["missing_dead"][sel]
    D, n = R.shape
    lost_i = np.where(md & (hyp == "pessimistic"), exit_i + 1, -1)   # 悲觀：最後可得價之後一天歸零
    ex = np.where(md & (hyp == "pessimistic"), -1, exit_i)          # 悲觀者不以最後價出場
    h = np.full(n, (1.0 / n) * (1.0 - buy_c))
    alive = np.ones(n, dtype=bool)
    cash, turnover = 0.0, 1.0
    nav = np.empty(D)
    for d in range(D):
        h = h * (1.0 + R[d])
        lz = lost_i == d
        if lz.any():
            h[lz] = 0.0
            alive[lz] = False
        xz = ex == d
        if xz.any():
            cash += float(h[xz].sum()) * (1.0 - sell_c)
            turnover += float(h[xz].sum())
            h[xz] = 0.0
            alive[xz] = False
        if rebalance and d > 0 and d % REBAL == 0 and d < D - 1:
            tr = alive & has_px[d]
            k = int(tr.sum())
            if k:
                held = float(h[alive & ~tr].sum())
                V = cash + float(h[tr].sum())
                tgt = V / k
                delta = tgt - h[tr]
                cost = buy_c * float(delta[delta > 0].sum()) - sell_c * float(delta[delta < 0].sum())
                tgt = (V - cost) / k
                delta = tgt - h[tr]
                turnover += float(np.abs(delta).sum()) / max(V + held, 1e-12)
                h[tr] = tgt
                cash = 0.0
        nav[d] = cash + float(h.sum())
    return nav, turnover


# ------------------------------------------------------------------ 指標
def cagr(nav: np.ndarray, cal: pd.DatetimeIndex) -> float:
    yrs = (cal[-1] - T0).days / 365.25
    return float(nav[-1] ** (1 / yrs) - 1) if nav[-1] > 0 else -1.0


def mdd(nav: np.ndarray) -> float:
    peak = np.maximum.accumulate(nav)
    return float((nav / peak - 1).min())


def seg_mdd(nav: np.ndarray, cal: pd.DatetimeIndex, a: str, b: str) -> float:
    m = (cal >= pd.Timestamp(a)) & (cal <= pd.Timestamp(b))
    return mdd(nav[m]) if m.any() else float("nan")


def period_returns(nav: np.ndarray, cal: pd.DatetimeIndex) -> dict:
    out = {}
    full = np.concatenate([[1.0], nav])  # 起點＝t0 買入前的 1 元
    dates = [T0 - pd.Timedelta(days=1)] + list(cal)
    for name, a, b in PERIODS:
        start = max(i for i, dd in enumerate(dates) if dd < pd.Timestamp(a)) if pd.Timestamp(a) > T0 else 0
        end = max(i for i, dd in enumerate(dates) if dd <= pd.Timestamp(b))
        out[name] = float(full[end] / full[start] - 1)
    return out


def costs_legs(mult: float) -> tuple[float, float]:
    from validation import costs as C
    rt = C.round_trip_cost_pct()
    buy = C.COMMISSION_RATE + C.DEFAULT_SLIPPAGE_BPS / 10000.0
    return buy * mult, (rt - buy) * mult


# ------------------------------------------------------------------ 判定
def evaluate(M: dict, cal: pd.DatetimeIndex, hyp: str, cagr50: float) -> dict:
    n = len(M["codes"])
    allsel = np.ones(n, dtype=bool)
    res = {"hypothesis": hyp}
    navs = {}
    for mult in (1, 2, 3):
        b, s = costs_legs(mult)
        ns, to_s = simulate(M, allsel, True, hyp, b, s)
        nb, to_b = simulate(M, allsel, False, hyp, b, s)
        navs[mult] = (ns, nb)
        res[f"cost_{mult}x"] = {"strategy_cagr": cagr(ns, cal), "benchmark_cagr": cagr(nb, cal),
                                "premium_cagr": cagr(ns, cal) - cagr(nb, cal),
                                "strategy_total": float(ns[-1] - 1), "benchmark_total": float(nb[-1] - 1),
                                "strategy_turnover_sum": to_s, "benchmark_turnover_sum": to_b}
    ns, nb = navs[1]
    surv = {"strategy_full": mdd(ns), "benchmark_full": mdd(nb)}
    for k, (a, bb) in BEARS.items():
        surv[f"strategy_{k}"] = seg_mdd(ns, cal, a, bb)
        surv[f"benchmark_{k}"] = seg_mdd(nb, cal, a, bb)
    res["drawdowns_1x"] = surv
    res["survival_violated"] = bool(any(v < SURV_LIMIT for v in surv.values()))
    ps, pb = period_returns(ns, cal), period_returns(nb, cal)
    res["periods_1x"] = {k: {"strategy": ps[k], "benchmark": pb[k], "premium": ps[k] - pb[k]} for k in ps}
    n_pos = sum(1 for k in ps if ps[k] - pb[k] > 0)
    b1, s1 = costs_legs(1)
    rnd = []
    for i in range(N_RANDOM):
        rng = np.random.default_rng(SEED0 + i)
        sel = np.zeros(n, dtype=bool)
        sel[rng.choice(n, n // 2, replace=False)] = True
        a1, _ = simulate(M, sel, True, hyp, b1, s1)
        a2, _ = simulate(M, sel, False, hyp, b1, s1)
        rnd.append(cagr(a1, cal) - cagr(a2, cal))
    frac = float(np.mean(np.array(rnd) > 0))
    res["random_half_control"] = {"n": N_RANDOM, "frac_premium_positive": frac, "min": float(min(rnd)),
                                  "median": float(np.median(rnd)), "max": float(max(rnd))}
    daily = ns[1:] / ns[:-1] - 1
    res["daily_stats_strategy_1x"] = {"sharpe_daily": float(daily.mean() / daily.std(ddof=1)), "n_obs": int(len(daily)),
                                      "skew": float(pd.Series(daily).skew()), "kurtosis": float(pd.Series(daily).kurt() + 3.0)}
    gates = {
        "g1_premium_1x_pos": res["cost_1x"]["premium_cagr"] > 0,
        "g2_random_ge_95": frac >= 0.95,
        "g3_periods_ge_7_of_8": n_pos >= 7,
        "g4_premium_3x_pos": res["cost_3x"]["premium_cagr"] > 0,
        "g5_gate8_beats_0050": res["cost_1x"]["strategy_cagr"] > cagr50,
    }
    res["n_periods_positive"] = n_pos
    res["gates"] = {k: bool(v) for k, v in gates.items()}
    res["verdict"] = "VIOLATES_SURVIVAL" if res["survival_violated"] else ("PASS" if all(gates.values()) else "FAIL")
    return res


def disclosures(codes: set[str], meta: dict) -> dict:
    rep = json.loads(FILL_REPORT.read_text(encoding="utf-8"))
    inwin = lambda r, key: (r.get("stock_id", r.get("code")) in codes) and str(T0.date()) <= str(r.get(key, ""))[:10] <= CUTOFF  # noqa: E731
    z = [r for r in rep["assumed_zero_return_list"] if inwin(r, "resume_date")]
    j = [r for r in rep["jumps_over_20pct"] if inwin(r, "resume_date")]
    g = [r for r in rep["gap_scan_suspects_not_added"] if inwin(r, "resume_date")]
    imp = [r for r in rep["impossible"] if inwin(r, "to")]
    return {"source": "research/data/v1_reduction_fill_report.json（只列 t0 母體股、恢復日在 2007-07-02～2014-12-31）",
            "assumed_zero_return": {"n": len(z), "n_report_total": len(rep["assumed_zero_return_list"]), "list": z},
            "jumps_over_20pct": {"n": len(j), "n_report_total": len(rep["jumps_over_20pct"]), "list": j},
            "unresolved_suspects_not_adjusted": {"n": len(g), "n_report_total": rep["n_gap_scan_suspects_not_added"], "list": g},
            "impossible": {"n": len(imp), "n_report_total": rep["n_impossible"], "list": imp},
            "events_errors": {c: m["events_error"] for c, m in meta.items() if m["events_error"]}}


def run() -> int:
    if RESULT.exists():
        print(f"拒跑：結果檔已存在（{RESULT}）——V1 只跑一次（PREREG 定稿條文 7）")
        return 2
    install_no_network_guard()
    t_start = datetime.now()
    data = build_data()
    cal, series, meta = data["cal"], data["series"], data["meta"]
    codes = sorted(series)
    M = make_matrix(series, cal, codes, meta)
    a50 = data["a50"].reindex(cal).ffill()
    base50 = data["a50"][data["a50"].index <= T0].iloc[-1]
    nav50 = (a50 / base50).to_numpy()
    cagr50 = cagr(nav50, cal)
    out = {"trial_parent": 462, "prereg": PREREG, "prereg_commit": PREREG_COMMIT,
           "generated_at": datetime.now().isoformat(timespec="seconds"), "window": [str(T0.date()), str(cal[-1].date())],
           "n_trading_days": len(cal), "n_universe": len(codes),
           "n_delisted_in_universe": int(sum(meta[c]["dead"] for c in codes)),
           "n_missing_data_delisted": int(M["missing_dead"].sum()),
           "missing_data_delisted": [c for c, f in zip(codes, M["missing_dead"]) if f],
           "n_alive_price_ends_early": int(M["early_alive"].sum()),
           "alive_price_ends_early": [c for c, f in zip(codes, M["early_alive"]) if f],
           "n_stocks_with_supp_reduction_events": int(sum(1 for c in codes if meta[c]["supp_events"])),
           "benchmark_0050": {"cagr_total_return": cagr50, "mdd": mdd(nav50), "n_events": data["n_ev50"], "events_error": data["err50"]},
           "cost_legs_1x": dict(zip(("buy", "sell"), costs_legs(1))),
           "cache_missing_datasets": {k: [d for d, v in u.items() if v is None] for k, u in CACHE_USE.items()
                                      if any(v is None for v in u.values())},
"cache_late_start": {ds: sorted(k for k, u in CACHE_USE.items() if u.get(ds) and u[ds][:10] > "2007-07-01")
                                for ds in ("TaiwanStockPrice", "TaiwanStockDividend")},
           "discretion": __doc__.split("[自行裁量]")[1].split("用法：")[0].strip()}
    out["coverage_check_vs_prereg"] = {"prereg_universe": 1253, "prereg_delisted": 75,
                                       "match": out["n_universe"] == 1253 and out["n_delisted_in_universe"] == 75}
    out["results"] = {h: evaluate(M, cal, h, cagr50) for h in ("pessimistic", "neutral")}
    v = [out["results"][h]["verdict"] for h in ("pessimistic", "neutral")]
    out["verdict"] = "VIOLATES_SURVIVAL" if "VIOLATES_SURVIVAL" in v else ("PASS" if v == ["PASS", "PASS"] else "FAIL")
    out["disclosures"] = disclosures(set(codes), meta)
    out["elapsed_sec"] = round((datetime.now() - t_start).total_seconds(), 1)
    RESULT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    brief = {k: out[k] for k in ("n_universe", "n_delisted_in_universe", "n_missing_data_delisted", "verdict", "elapsed_sec")}
    print(json.dumps(brief, ensure_ascii=False))
    for h in ("pessimistic", "neutral"):
        r = out["results"][h]
        print(h, r["verdict"], json.dumps({"gates": r["gates"], "1x": r["cost_1x"], "dd": r["drawdowns_1x"],
                                           "rand": r["random_half_control"], "periods+": r["n_periods_positive"]}, ensure_ascii=False))
    print("0050", json.dumps(out["benchmark_0050"], ensure_ascii=False))
    return 0


# ------------------------------------------------------------------ 單發前資料探測（只看母體／涵蓋／跳動數，不算任何報酬）
PROBE = HERE / "data" / "var1018_v1_r2_probe.json"


def probe() -> int:
    """修訂 R2 後重做資料探測（先.一三三-1a 定案條件）：母體檔數、下市股、缺資料下市股、相鄰交易日還原收盤 >±7.5% 筆數。
    不呼叫 simulate／evaluate，不算策略或基準報酬。"""
    install_no_network_guard()
    data = build_data()
    cal, series, meta = data["cal"], data["series"], data["meta"]
    codes = sorted(series)
    M = make_matrix(series, cal, codes, meta)
    jumps = []
    for c in codes:
        s = series[c]
        s = s[(s.index >= T0) & (s.index <= END)]
        pos = pd.Series(np.arange(len(cal)), index=cal).reindex(s.index)
        r = s.pct_change()
        adj = (pos.diff() == 1) & (r.abs() > 0.075)
        for d in s.index[adj.to_numpy()]:
            jumps.append({"stock_id": c, "date": str(d.date()), "ret": round(float(r[d]), 4)})
    by_year: dict[str, int] = {}
    for j in jumps:
        by_year[j["date"][:4]] = by_year.get(j["date"][:4], 0) + 1
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "returns_computed": False, "zero_requests": True,
           "n_universe": len(codes), "n_delisted_in_universe": int(sum(meta[c]["dead"] for c in codes)),
           "n_missing_data_delisted": int(M["missing_dead"].sum()),
           "missing_data_delisted": [c for c, f in zip(codes, M["missing_dead"]) if f],
           "n_alive_price_ends_early": int(M["early_alive"].sum()),
           "alive_price_ends_early": [c for c, f in zip(codes, M["early_alive"]) if f],
           "n_adjacent_moves_over_7p5pct": len(jumps), "n_adjacent_stocks": len({j["stock_id"] for j in jumps}),
           "adjacent_by_year": dict(sorted(by_year.items())),
           "adjacent_list": sorted(jumps, key=lambda j: -abs(j["ret"]))[:200],
           "events_errors": {c: m["events_error"] for c, m in meta.items() if m["events_error"]},
           "n_trading_days": len(cal)}
    PROBE.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if not isinstance(v, (list, dict)) or k == "adjacent_by_year"}, ensure_ascii=False))
    return 0


# ------------------------------------------------------------------ 自測（合成資料，不碰真資料報酬）
def selftest() -> int:
    ok = True
    cal = pd.bdate_range("2007-07-02", periods=50)
    # 兩檔：A 每天 +1%、B 每天 −1%；再平衡應該把錢從 A 移到 B
    R = np.zeros((50, 2))
    R[1:, 0], R[1:, 1] = 0.01, -0.01
    M = {"R": R, "has_px": np.ones((50, 2), bool), "exit_i": np.array([-1, -1]), "missing_dead": np.array([False, False]),
         "codes": ["A", "B"]}
    nb, _ = simulate(M, np.ones(2, bool), False, "neutral", 0.0, 0.0)
    exp_b = 0.5 * 1.01 ** 49 + 0.5 * 0.99 ** 49
    ok &= abs(nb[-1] - exp_b) < 1e-9
    ns, _ = simulate(M, np.ones(2, bool), True, "neutral", 0.0, 0.0)
    ok &= ns[-1] < nb[-1]  # A 漲 B 跌、趨勢持續時再平衡吃虧
    # 下市：B 在第 10 天最後一筆、缺資料。悲觀第 11 天歸零；中性第 10 天出場持現金
    M2 = dict(M, exit_i=np.array([-1, 10]), missing_dead=np.array([False, True]))
    npes, _ = simulate(M2, np.ones(2, bool), False, "pessimistic", 0.0, 0.0)
    nneu, _ = simulate(M2, np.ones(2, bool), False, "neutral", 0.0, 0.0)
    ok &= abs(nneu[-1] - (0.5 * 1.01 ** 49 + 0.5 * 0.99 ** 10)) < 1e-9
    ok &= abs(npes[-1] - 0.5 * 1.01 ** 49) < 1e-9
    # 成本：零報酬、只買一次，淨值＝1−buy
    M3 = dict(M, R=np.zeros((50, 2)))
    nc, _ = simulate(M3, np.ones(2, bool), False, "neutral", 0.002, 0.004)
    ok &= abs(nc[-1] - 0.998) < 1e-12
    # 指標
    ok &= abs(mdd(np.array([1.0, 2.0, 1.0, 1.5])) + 0.5) < 1e-12
    pr = period_returns(np.linspace(1.0, 1.1, len(cal)), cal)
    ok &= abs(pr["2007H2"] - 0.1) < 1e-9
    # 還原：ex_date 以前乘 factor
    s = pd.Series([10.0, 10.0, 5.0], index=pd.to_datetime(["2008-01-02", "2008-01-03", "2008-01-04"]))
    a = apply_events(s, pd.DataFrame([{"ex_date": "2008-01-04", "factor": 0.5}]))
    ok &= list(a.values) == [5.0, 5.0, 5.0]
    # 無網路守門
    install_no_network_guard()
    try:
        F._fetch("TaiwanStockPrice", "9999", "1900-01-01", "1900-01-02")
        ok = False
    except NoNetwork:
        pass
    # 快取轉接不讀 latest 檔、截到 2014-12-31
    df = local_load_dev("TaiwanStockPrice", "0050", "2006-01-01")
    ok &= (not df.empty) and df["date"].max() <= CUTOFF
    print("selftest", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "selftest"
    raise SystemExit(run() if cmd == "run" else probe() if cmd == "probe" else selftest())
