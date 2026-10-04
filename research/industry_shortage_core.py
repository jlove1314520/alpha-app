"""先.十三-三：產業缺貨方向——計分（桶層級）／桶選擇／個股選取／模擬共用邏輯。

事前綁定定義對應 `docs/PREREG_industry_shortage_FINAL.md` §2～§3。
重用 `supply_tightness_core.Panel`／`Sim`／`rates` 等既有模擬引擎（面板母體沿用 #406，
`[自行裁量]` 2，見 FINAL §7-2）。本檔只新增「桶分數→選桶→選股（流動性截斷）」這段，
不重寫任何既有回測引擎（符合十三節「核心研究檔案單一寫入者」——本檔不在
`research/backtest/`／`research/validation/` 範圍內，是本方向專屬的草稿期腳本）。
"""
from __future__ import annotations

import csv
import glob
import pickle
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import supply_tightness_core as C  # noqa: E402
from industry_shortage_mapping import BUCKETS  # noqa: E402

ROOT = HERE.parent
PIT = ROOT / "data" / "moea_pit"
PANEL_PATH = HERE / "data" / "supply_tightness_panel.pkl"
STOCK_MAP = ROOT / "docs" / "industry_shortage_stock_map.csv"
LIQ_PATH = HERE / "data" / "industry_shortage_liquidity.pkl"

MIN_BUCKET = 8          # 桶內活躍股下限（§2(b)）
GATE_BUCKETS = 10       # 關1：每換股日有訊號桶數下限
K_SEL = 3                # 入選桶數（§2(c)）
N_HOLD = 20              # 持股上限（§2(c)）
VAL_END = C.VAL_END


def roc_to_period(s):
    s = str(s).strip()
    return pd.Period(f"{int(s[:-2]) + 1911}-{s[-2:]}", "M")


def load_a():
    f = sorted(glob.glob(str(PIT / "A" / "製造業存貨率" / "*.csv")))[-1]
    d = defaultdict(dict)
    for r in csv.DictReader(open(f, encoding="utf-8-sig")):
        try:
            d[r["行業代碼"]][roc_to_period(r["資料期(民國年)"])] = float(r["統計值(比率)"])
        except ValueError:
            pass
    return d


def load_c(name):
    f = sorted(glob.glob(str(PIT / "C" / f"外銷訂單_{name}" / "*.csv")))[-1]
    d = {}
    for r in csv.DictReader(open(f, encoding="utf-8-sig")):
        if r["統計項目"] != "外銷訂單金額_美元":
            continue
        try:
            d[roc_to_period(r["資料期(民國年)"])] = float(r["統計值(金額)"])
        except ValueError:
            pass
    return d


def load_all_c():
    names = sorted({c for b in BUCKETS for c in b["c"]})
    return {n: load_c(n) for n in names}


def sa_value(A, codes, T):
    xs0, xs1 = [], []
    for c in codes:
        s = A.get(c, {})
        if T not in s or (T - 12) not in s:
            return np.nan
        xs0.append(s[T])
        xs1.append(s[T - 12])
    return -(np.mean(xs0) - np.mean(xs1))


def sc_value(Cs_name, T, window=3):
    cur = [Cs_name.get(T - k) for k in range(window)]
    prv = [Cs_name.get(T - 12 - k) for k in range(window)]
    if any(v is None for v in cur + prv):
        return np.nan
    p = sum(prv)
    return sum(cur) / p - 1 if p > 0 else np.nan


def zscore_1_99(v):
    v = np.asarray(v, float)
    fin = np.isfinite(v)
    out = np.full(len(v), np.nan)
    if fin.sum() < 2:
        return out
    lo, hi = np.quantile(v[fin], [0.01, 0.99])
    w = np.clip(v, lo, hi)
    sd = np.nanstd(w[fin], ddof=1)
    if sd > 0:
        out[fin] = (w[fin] - np.nanmean(w[fin])) / sd
    return out


def load_stock_map():
    sm = pd.read_csv(STOCK_MAP, dtype=str)
    sm = sm[sm["status"] == "mapped"]
    return {r.stock_id: r.bucket_id for r in sm.itertuples() if len(r.stock_id) == 4}


def load_liquidity():
    with open(LIQ_PATH, "rb") as f:
        return pickle.load(f)["data"]


class BucketData:
    """桶分數所需的靜態資料（A/C 時間序列、個股→桶對照、流動性）。"""

    def __init__(self, P: "C.Panel"):
        self.A = load_a()
        self.Cs = load_all_c()
        code2bucket = load_stock_map()
        self.bnames = [b["id"] for b in BUCKETS]
        bpos = {b: i for i, b in enumerate(self.bnames)}
        self.sb = np.array([bpos.get(code2bucket.get(c), -1) for c in P.codes])
        self.liq = load_liquidity()
        self.liq_codes = P.codes

    def bucket_score_cnt(self, P: "C.Panel", r: int, R: pd.Period,
                          sc_window: int = 3, lag_months: int = 2):
        """回傳 (score[13], cnt[13], elig[13])；T = R - lag_months。"""
        T = R - lag_months
        alive = P.snapshot(r)["alive"]
        sa = np.array([sa_value(self.A, [c for c, _ in b["a"]], T) for b in BUCKETS])
        sc = np.array([sc_value(self.Cs[b["c"][0]], T, sc_window) if b["c"] else np.nan for b in BUCKETS])
        za, zc = zscore_1_99(sa), zscore_1_99(sc)
        with np.errstate(all="ignore"):
            stack = np.vstack([za, zc])
            n_av = np.isfinite(stack).sum(0)
            score = np.where(n_av > 0, np.nansum(stack, 0) / np.maximum(n_av, 1), np.nan)
        cnt = np.array([int(((self.sb == i) & alive).sum()) for i in range(len(self.bnames))])
        elig = (cnt >= MIN_BUCKET) & np.isfinite(score)
        return score, cnt, elig

    def liquidity_at(self, d: pd.Timestamp, pool_idx: np.ndarray) -> np.ndarray:
        """回傳 pool_idx 對應個股在 d 之前（不含 d）最近一筆近60日均額；無資料者 -inf。"""
        d64 = np.datetime64(d.normalize())
        out = np.full(len(pool_idx), -np.inf)
        for k, j in enumerate(pool_idx):
            c = self.liq_codes[j]
            ent = self.liq.get(c)
            if ent is None:
                continue
            dates = ent["dates"]
            idx = int(np.searchsorted(dates, d64, side="left")) - 1
            if idx >= 0:
                v = ent["roll60"][idx]
                if np.isfinite(v):
                    out[k] = v
        return out

    def precompute_liquidity_matrix(self, P: "C.Panel", rows: list[int]) -> np.ndarray:
        """一次性計算 rows（換股日列索引）× N 全個股的流動性代理矩陣（-inf＝無資料），
        供重複多次（bootstrap／隨機對照）選股共用，避免每次呼叫都重算。"""
        query = np.array([np.datetime64(P.cal[r].normalize()) for r in rows])
        mat = np.full((len(rows), P.N), -np.inf)
        for j, c in enumerate(self.liq_codes):
            ent = self.liq.get(c)
            if ent is None:
                continue
            idxs = np.searchsorted(ent["dates"], query, side="left") - 1
            valid = idxs >= 0
            if not valid.any():
                continue
            vals = np.full(len(rows), np.nan)
            vals[valid] = ent["roll60"][idxs[valid]]
            fin = np.isfinite(vals)
            mat[fin, j] = vals[fin]
        return mat


def rebalance_rows(P: "C.Panel", start="2014-04", end="2024-12"):
    """每月 26 日起第一個交易日；無此交易日者該月不換股（延續前一組持股）。"""
    out = []
    for R in pd.period_range(start, end, freq="M"):
        ds_mask = (P.cal.year == R.year) & (P.cal.month == R.month) & (P.cal.day >= 26)
        idxs = np.flatnonzero(ds_mask)
        if len(idxs) == 0:
            continue
        r = int(idxs[0])
        if P.cal[r] > VAL_END:
            continue
        out.append((r, R))
    return out


def select_buckets(score, elig, k=K_SEL):
    cand = np.flatnonzero(elig)
    if len(cand) == 0:
        return []
    order = cand[np.argsort(-score[cand], kind="stable")]
    return [int(x) for x in order[:k]]


def pick_stocks(P: "C.Panel", BD: BucketData, r: int, bucket_idxs: list[int], n_hold=N_HOLD, liq_row=None):
    if not bucket_idxs:
        return np.array([], dtype=int)
    alive = P.snapshot(r)["alive"]
    mask = alive & np.isin(BD.sb, bucket_idxs)
    pool = np.flatnonzero(mask)
    if len(pool) == 0:
        return pool
    liq = liq_row[pool] if liq_row is not None else BD.liquidity_at(P.cal[r], pool)
    order = np.argsort(-liq, kind="stable")
    return pool[order[:n_hold]]


def precompute_dates(P: "C.Panel", BD: BucketData, rc_rows, sc_window=3, lag_months=2):
    """每個換股日的桶分數＋流動性代理只算一次，供 bootstrap／隨機對照重複使用
    （避免重算 A/C 分數、避免重複掃流動性 pickle）。"""
    rows_only = [r for r, _ in rc_rows]
    liq_mat = BD.precompute_liquidity_matrix(P, rows_only)
    out = []
    for i, (r, R) in enumerate(rc_rows):
        score, cnt, elig = BD.bucket_score_cnt(P, r, R, sc_window, lag_months)
        out.append({"r": r, "R": R, "score": score, "cnt": cnt, "elig": elig, "liq_row": liq_mat[i]})
    return out


def make_sels(P: "C.Panel", BD: BucketData, cache, k=K_SEL, n_hold=N_HOLD, bucket_inc=None, random_rng=None):
    """cache：`precompute_dates()` 的輸出。bucket_inc：長度13的bool mask，限制可入選桶集合（cluster bootstrap用）。
    random_rng 非 None 時改為隨機抽 k 個 elig（且在 bucket_inc 內）桶，而非取分數最高（gate5 隨機對照用）。
    回傳 (rows, sels, per_date)。
    """
    rows, sels, per_date = [], [], []
    for c in cache:
        r, score, cnt, elig = c["r"], c["score"], c["cnt"], c["elig"]
        e = elig.copy()
        if bucket_inc is not None:
            e &= bucket_inc
        if random_rng is not None:
            cand = np.flatnonzero(e)
            chosen = [int(x) for x in random_rng.choice(cand, min(k, len(cand)), replace=False)] if len(cand) else []
        else:
            chosen = select_buckets(score, e, k)
        sel = pick_stocks(P, BD, r, chosen, n_hold, liq_row=c.get("liq_row"))
        rows.append(r)
        sels.append(sel)
        per_date.append({"r": r, "n_elig_buckets": int(elig.sum()), "n_scorable_alive": int(cnt[elig].sum()) if elig.any() else 0,
                         "chosen_buckets": chosen, "n_selected_stocks": int(len(sel))})
    return rows, sels, per_date


def run_from_cache(P: "C.Panel", BD: BucketData, cache, cost=1.0, k=K_SEL, n_hold=N_HOLD,
                    bucket_inc=None, random_rng=None):
    rows, sels, per_date = make_sels(P, BD, cache, k, n_hold, bucket_inc, random_rng)
    br, sr = C.rates(cost)
    eq, st = C.Sim(P, br, sr, w=1.0 / n_hold).run(rows, sels)
    return {"eq": eq, "st": st, "sels": sels, "r0": rows[0], "br": br, "sr": sr, "rows": rows, "per_date": per_date}


def run_cfg(P: "C.Panel", BD: BucketData, rc_rows, cost=1.0, k=K_SEL, n_hold=N_HOLD, sc_window=3, lag_months=2,
            bucket_inc=None, random_rng=None):
    """未快取版本：供敏感度分析（換 sc_window／lag_months 等需要重算分數的場合）使用。"""
    cache = precompute_dates(P, BD, rc_rows, sc_window, lag_months)
    return run_from_cache(P, BD, cache, cost, k, n_hold, bucket_inc, random_rng)
