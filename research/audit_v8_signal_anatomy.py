# -*- coding: utf-8 -*-
"""驗.八 二（析.一）：EPS／營收訊號拆解（2026-09-29總司令裁示【驗.八（修正版）】）。

**診斷，不是新試驗，不改任何判定、不登記試驗編號、不寫TRIALS_REGISTRY。**
樣本、期間與#401~#404重驗一致：`factor_ic.sample_universe_ids(300, 20260822)`、
2015-01-01~VAL_END（holdout一律不碰，`load_dev`已cap在VAL_END）。

三件事：
1. 舊PIT（季報期末+45日，即Q4在2/14就可得）下，`f_eps_surprise`／
   `f_revenue_surprise`的20日前瞻IC，拆成(a)as_of落在Q4前視窗（每年2/14~3/31）
   與(b)其餘日期，各報IC與樣本數。舊PIT只影響Q4：Q1~Q3的期末+45日剛好等於
   法定期限（5/15、8/14、11/14），所以「舊PIT」＝把pit.statutory_quarterly_pit_date
   暫時換成期末+45日。月營收PIT（month_revenue_pit）新舊相同，故營收因子的
   「舊PIT」與「正確PIT」是同一條序列，拆窗結果本身就是它的對照。
2. 正確PIT下，事件時間IC衰減曲線：以公告日（PIT可得日）當日收盤進場，往後
   1/5/10/20/60個交易日的橫斷面Spearman IC（同公告日的所有股票為一個橫斷面）。
3. `f_revenue_surprise`與`f_low_vol`（另附`f_eps_surprise`）的橫斷面相關。

輸出：research/data/diag_v8_signal_anatomy.json
"""
from __future__ import annotations

import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

import factor_ic as fic
import factors as fx
import pit as pit_mod
from adjust import adjusted_price_series
from validation import holdout

OUT = Path(__file__).parent / "data" / "diag_v8_signal_anatomy.json"
START = fic.START_DATE
SNAP_START = fic.SNAPSHOT_START
HORIZON = 20
DECAY_H = [1, 5, 10, 20, 60]
MIN_XS = 10
N_NULL = 500
NULL_SEED = 20260929


def _old_pit_date(period_end) -> pd.Timestamp:
    return pd.Timestamp(period_end) + pd.Timedelta(days=45)


def in_q4_window(date_str: str) -> bool:
    return "02-14" <= date_str[5:] <= "03-31"


def _build_stock(sid: str):
    px = adjusted_price_series(sid, START)
    if px.empty or len(px) < 260:
        return None
    d = px.sort_values("date").reset_index(drop=True).copy()
    eps_new = fx._eps_surprise_sue(sid, START)
    rev = fx._revenue_surprise_sue(sid, START)
    real = pit_mod.statutory_quarterly_pit_date
    pit_mod.statutory_quarterly_pit_date = _old_pit_date
    try:
        eps_old = fx._eps_surprise_sue(sid, START)
    finally:
        pit_mod.statutory_quarterly_pit_date = real
    d = fx._asof_join(d, eps_new, "eps_sue", "f_eps_new")
    d = fx._asof_join(d, eps_old, "eps_sue", "f_eps_old")
    d = fx._asof_join(d, rev, "revenue_sue", "f_rev")
    d["f_lowvol"] = -d["adj_close"].pct_change().rolling(fx.LOW_VOL_WINDOW, min_periods=fx.LOW_VOL_WINDOW).std()
    return d, eps_new, eps_old, rev


def _rank_std(v: np.ndarray) -> np.ndarray:
    r = pd.Series(v).rank().to_numpy()
    r = r - r.mean()
    n = np.linalg.norm(r)
    return r / n if n > 0 else r * np.nan


def xs_ic(F: pd.DataFrame, R: pd.DataFrame, dates: list[str]) -> dict[str, tuple[float, int]]:
    out = {}
    for dt in dates:
        if dt not in F.index or dt not in R.index:
            continue
        f = F.loc[dt].to_numpy(dtype=float)
        r = R.loc[dt].to_numpy(dtype=float)
        m = ~(np.isnan(f) | np.isnan(r))
        if m.sum() < MIN_XS:
            continue
        ic, _ = spearmanr(f[m], r[m])
        if not np.isnan(ic):
            out[dt] = (float(ic), int(m.sum()))
    return out


def summarize(ics: dict[str, tuple[float, int]]) -> dict:
    if not ics:
        return {"n_dates": 0, "n_pairs": 0, "mean_ic": None, "ic_ir": None, "hit_rate": None, "t_naive": None}
    v = np.array([x[0] for x in ics.values()])
    n = np.array([x[1] for x in ics.values()])
    sd = float(v.std(ddof=1)) if len(v) > 1 else float("nan")
    mean = float(v.mean())
    return {
        "n_dates": int(len(v)), "n_pairs": int(n.sum()),
        "mean_ic": round(mean, 5),
        "ic_ir": round(mean / sd, 4) if sd and sd > 0 else None,
        "hit_rate": round(float(np.mean(np.sign(v) == np.sign(mean))), 3) if mean != 0 else None,
        "t_naive": round(mean / (sd / np.sqrt(len(v))), 2) if sd and sd > 0 else None,
    }


def null_pct(F: pd.DataFrame, R: pd.DataFrame, dates: list[str]) -> float | None:
    """shuffle-null分位：|全期mean IC|大於幾%的shuffle mean（同factor_ic框架的比法）。"""
    rng = np.random.default_rng(NULL_SEED)
    rf, rr = [], []
    for dt in dates:
        if dt not in F.index or dt not in R.index:
            continue
        f = F.loc[dt].to_numpy(dtype=float)
        r = R.loc[dt].to_numpy(dtype=float)
        m = ~(np.isnan(f) | np.isnan(r))
        if m.sum() < MIN_XS:
            continue
        a, b = _rank_std(f[m]), _rank_std(r[m])
        if np.isnan(a).any() or np.isnan(b).any():
            continue
        rf.append(a)
        rr.append(b)
    if not rf:
        return None
    obs = float(np.mean([a @ b for a, b in zip(rf, rr)]))
    null = np.zeros(N_NULL)
    for a, b in zip(rf, rr):
        perm = rng.permuted(np.tile(a, (N_NULL, 1)), axis=1)
        null += perm @ b
    null /= len(rf)
    return round(100.0 * float(np.mean(abs(obs) > np.abs(null))), 1)


def main() -> None:
    sample_ids = fic.sample_universe_ids(fic.SAMPLE_SIZE, fic.SAMPLE_SEED)
    print(f"[析.一] 樣本{len(sample_ids)}檔，載入中...", flush=True)
    per_stock, ev_eps, ev_rev = {}, {}, {}
    for i, sid in enumerate(sample_ids):
        try:
            res = _build_stock(sid)
        except Exception as e:  # noqa: BLE001
            print(f"  {sid}: ERROR {e}", flush=True)
            continue
        if res is None:
            continue
        d, eps_new, _eps_old, rev = res
        per_stock[sid] = d.set_index("date")
        ev_eps[sid] = eps_new
        ev_rev[sid] = rev
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(sample_ids)}", flush=True)
    sids = list(per_stock)
    print(f"  可用{len(sids)}檔", flush=True)

    def panel(col):
        return pd.concat({s: per_stock[s][col] for s in sids}, axis=1).sort_index()

    P = panel("adj_close")
    P = P[(P.index >= "2010-01-01") & (P.index <= holdout.VAL_END)]
    F_eps_new, F_eps_old = panel("f_eps_new").reindex(P.index), panel("f_eps_old").reindex(P.index)
    F_rev, F_lv = panel("f_rev").reindex(P.index), panel("f_lowvol").reindex(P.index)
    cal = [d for d in P.index if d >= SNAP_START]

    def fwd(h):
        return P.shift(-h) / P - 1

    R20 = fwd(HORIZON)
    # 20日前瞻報酬需要t+20的價格仍在VAL_END內：shift(-20)在尾端自然為NaN
    snap_dates = [a for a, _ in fic.build_snapshots(list(P.index), SNAP_START, holdout.VAL_END)]
    res = {"generated_at": pd.Timestamp.now().isoformat(),
           "verdict_locked_note": "診斷值，不是新試驗，不改任何既有判定，不登記TRIALS_REGISTRY。",
           "n_stocks": len(sids), "period": f"{SNAP_START}..{holdout.VAL_END}",
           "q4_window": "每年 02-14 ~ 03-31（含）"}

    # ---- 一、舊PIT拆窗 ----
    part1 = {}
    for label, F in (("f_eps_surprise_oldPIT", F_eps_old), ("f_eps_surprise_correctPIT", F_eps_new),
                     ("f_revenue_surprise", F_rev)):
        ics_all = xs_ic(F, R20, cal)
        ics_snap = xs_ic(F, R20, [d for d in snap_dates if d >= SNAP_START])
        sub = {}
        for gname, sel in (("a_Q4前視窗", in_q4_window), ("b_其餘", lambda s: not in_q4_window(s)), ("全部", lambda s: True)):
            sub[gname] = {
                "daily_overlapping": summarize({k: v for k, v in ics_all.items() if sel(k)}),
                "snapshots_20d_nonoverlap": summarize({k: v for k, v in ics_snap.items() if sel(k)}),
            }
        # 各年Q4窗內IC（舊PIT eps）看一致性
        by_year = {}
        for k, v in ics_all.items():
            if in_q4_window(k):
                by_year.setdefault(k[:4], []).append(v[0])
        sub["a_Q4前視窗_逐年平均IC"] = {y: round(float(np.mean(v)), 4) for y, v in sorted(by_year.items())}
        part1[label] = sub
    # eps：同日期舊PIT vs 正確PIT在窗內的IC差（純前視貢獻）
    part1["_note_revenue"] = "月營收PIT新舊相同；營收因子的舊PIT=正確PIT，同一條序列。"
    res["part1_q4_window_split"] = part1

    # ---- 二、正確PIT事件時間衰減 ----
    idx = list(P.index)
    idx_arr = np.array(idx)

    def event_panel(ev_map, kind):
        E = pd.DataFrame(np.nan, index=P.index, columns=sids)
        col = "eps_sue" if kind == "eps" else "revenue_sue"
        for s, pdf in ev_map.items():
            if pdf.empty or col not in pdf.columns:
                continue
            q = pdf.dropna(subset=[col])
            for _, row in q.iterrows():
                pos = int(np.searchsorted(idx_arr, row["pit_date"], side="left"))
                if pos >= len(idx_arr) or idx_arr[pos] < SNAP_START:
                    continue
                E.iat[pos, sids.index(s)] = float(row[col])
        return E

    part2 = {}
    for label, ev_map, kind in (("f_eps_surprise", ev_eps, "eps"), ("f_revenue_surprise", ev_rev, "rev")):
        E = event_panel(ev_map, kind)
        ev_dates = [d for d in P.index if E.loc[d].notna().sum() >= MIN_XS and d >= SNAP_START]
        curve = {}
        for h in DECAY_H:
            ics = xs_ic(E, fwd(h), ev_dates)
            allv = summarize(ics)
            tr = summarize({k: v for k, v in ics.items() if k <= holdout.TRAIN_END})
            va = summarize({k: v for k, v in ics.items() if holdout.TRAIN_END < k <= holdout.VAL_END})
            allv["null_percentile"] = null_pct(E, fwd(h), list(ics))
            curve[f"h={h}"] = {"all": allv, "train": tr, "val": va}
        entry = {"event_dates": len(ev_dates), "curve": curve}
        if kind == "eps":
            byq = {}
            mon = {1: (5,), 2: (8,), 3: (11,), 4: (3, 4)}
            for q in (1, 2, 3, 4):
                dts = [d for d in ev_dates if int(d[5:7]) in mon[q]]
                byq[f"Q{q}期報告(公告日月份{'/'.join(map(str, mon[q]))})"] = {
                    f"h={h}": summarize(xs_ic(E, fwd(h), dts)) for h in (5, 20, 60)
                }
            entry["by_report_quarter"] = byq
        part2[label] = entry
    res["part2_event_decay_correctPIT"] = part2

    # ---- 三、相關 ----
    def corr_pair(A, B, dates):
        ics = xs_ic(A, B, dates)
        return summarize(ics)

    part3 = {}
    for name, A, B in (("f_revenue_surprise vs f_low_vol", F_rev, F_lv),
                       ("f_eps_surprise(正確PIT) vs f_low_vol", F_eps_new, F_lv),
                       ("f_revenue_surprise vs f_eps_surprise(正確PIT)", F_rev, F_eps_new)):
        ics = xs_ic(A, B, cal)
        ics_s = xs_ic(A, B, [d for d in snap_dates if d >= SNAP_START])
        by_year = {}
        for k, v in ics.items():
            by_year.setdefault(k[:4], []).append(v[0])
        part3[name] = {"daily": summarize(ics), "snapshots_20d": summarize(ics_s),
                       "逐年平均": {y: round(float(np.mean(v)), 3) for y, v in sorted(by_year.items())},
                       "std_across_dates": round(float(np.std([v[0] for v in ics.values()], ddof=1)), 3)}
    res["part3_cross_sectional_corr"] = part3

    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"\n已寫入 {OUT}")


if __name__ == "__main__":
    main()
