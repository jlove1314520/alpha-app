"""補.研究-個股期貨基差 單發（TRIALS #460，PREREG docs/PREREG_STOCK_FUTURES_BASIS_FINAL.md）。

期貨比合理價 F*＝S×(1+r×τ/365)−已公告股利 貴 ≥k 時，t+1 收盤買現貨 1 口份（2,000 股）＋賣期貨 1 口，
持有到最後交易日。只做期貨偏貴一邊（無放空現貨腿）。判定期 2010-01-25～2024-12-31，不碰 holdout。

兩種模式：
  python research/stock_futures_basis_oneshot.py --prep   # 只整備資料、印覆蓋率，不算任何報酬
  python research/stock_futures_basis_oneshot.py --run    # 唯一一次單發；結果檔已存在就拒跑

資料（全部本機快取，--run 零請求）：
  期貨日行情：research/data/raw/taifex_fut_yearly/{年}.zip（期交所 futDataDown 年度檔）
  契約↔標的：research/data/raw/taifex_ssf/SSFLists.raw（期交所 OpenAPI /v1/SSFLists，現行名冊）；
             名冊裡沒有的舊契約用「近月收盤 / 現貨收盤」中位數比對（列出比對失敗清單）
  契約名稱（排除「小型」）：research/data/raw/taifex_ssf/FinalSettlementPriceSSF.raw
  現貨、股利：FinMind 本機快取 parquet
執行前附錄（PREREG 附錄 A，看結果前寫）：最後結算價歷史查不到 → 期貨腿以標的最後交易日收盤價結算；
  保證金與手續費沿用保守假設；期貨也收 5bps 滑價；遇契約調整（原契約提前消失）整組剔除並列數。
非投資建議。
"""
from __future__ import annotations

import calendar
import collections
import json
import math
import sys
import zipfile
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research"))
from validation.costs import COMMISSION_RATE, DEFAULT_SLIPPAGE_BPS, tax_rate  # noqa: E402
from validation.holdout import assert_no_holdout_leakage  # noqa: E402

RAW = ROOT / "research" / "data" / "raw"
FUT_DIR = RAW / "taifex_fut_yearly"
SSF_DIR = RAW / "taifex_ssf"
PREP_OUT = ROOT / "research" / "data" / "stock_futures_basis_prep.json"
RESULT_OUT = ROOT / "research" / "data" / "stock_futures_basis_oneshot_result.json"

START, END = "2010-01-25", "2024-12-31"
Q = 2000                      # 一般股票期貨契約乘數（股）
R_MAIN = 0.010                # 事前綁定外部常數（PREREG §3-1）
K_MAIN, TMIN_MAIN, OI_MIN, M_MAX = 0.010, 10, 100, 20
GRID_K = (0.007, 0.010, 0.013)
GRID_T = (7, 10, 13)
MARGIN_MAIN = 0.135           # 保守假設（歷史原始保證金比率查不到，PREREG §3-5）
FUT_TAX = 0.00002             # 期貨交易稅十萬分之二（保守假設，見 PREREG 附錄 A）
FUT_FEE = 80.0                # 每口每邊 NT$（保守值，非真實報價）
SLIP = DEFAULT_SLIPPAGE_BPS / 1e4
SPOT_TAX = tax_rate("normal")
N_RAND, SEED = 1000, 20261022


def _num(x):
    x = x.strip()
    if x in ("", "-"):
        return None
    try:
        return float(x)
    except ValueError:
        return None


def _third_wed(ym: str) -> date:
    y, m = int(ym[:4]), int(ym[4:6])
    c = calendar.Calendar()
    weds = [d for d in c.itermonthdates(y, m) if d.month == m and d.weekday() == 2]
    return weds[2]


# ── 契約名冊 ──
def load_registry():
    ssf = json.loads((SSF_DIR / "SSFLists.raw").read_bytes().decode("utf-8-sig"))
    reg = {x["Contract"]: x["StockCode"] for x in ssf if "普通股" in x.get("Type", "")}
    mini = set()
    for ln in (SSF_DIR / "FinalSettlementPriceSSF.raw").read_bytes().decode("utf-8-sig").splitlines()[1:]:
        p = ln.split(",")
        if len(p) >= 3 and "小型" in p[2]:
            mini.add(p[1].strip())
    return reg, mini


# ── 期貨日行情 ──
def load_futures() -> pd.DataFrame:
    cache = FUT_DIR / "_parsed_stock_like.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    rows = []
    for y in range(2010, 2025):
        z = zipfile.ZipFile(FUT_DIR / f"{y}.zip")
        for n in z.namelist():
            for ln in z.read(n).decode("big5", errors="replace").splitlines()[1:]:
                p = [x.strip() for x in ln.split(",")]
                if len(p) < 12:
                    continue
                code, ym = p[1], p[2]
                if len(code) != 3 or not code.endswith("F") or not ym.isdigit() or len(ym) != 6:
                    continue  # 排除調整型（*1/*2）、價差單、週契約
                if len(p) > 17 and p[17] and p[17] != "一般":
                    continue
                d = datetime.strptime(p[0], "%Y/%m/%d").date()
                rows.append((d, code, ym, _num(p[6]), _num(p[9]) or 0.0, _num(p[10]), _num(p[11]) or 0.0))
    df = pd.DataFrame(rows, columns=["date", "code", "ym", "close", "vol", "settle", "oi"])
    df["date"] = pd.to_datetime(df["date"])
    df = df[(df["date"] >= START) & (df["date"] <= END)].reset_index(drop=True)
    df.to_parquet(cache)
    return df


def load_spot(sid: str):
    """拼接該代號所有結束日 ≤2024-12-31 的快取檔（不讀 *__latest 檔，避免碰到 2025+）。"""
    parts = []
    for f in RAW.glob(f"TaiwanStockPrice__{sid}__*.parquet"):
        end = f.stem.split("__")[-1]
        if end == "latest" or end > END:
            continue
        try:
            parts.append(pd.read_parquet(f)[["date", "open", "max", "min", "close", "spread", "Trading_Volume"]])
        except Exception as e:  # 空檔／壞檔：略過，不影響其他檔
            print(f"[警告] 讀不到 {f.name}：{type(e).__name__}")
    if not parts:
        return None
    p = pd.concat(parts, ignore_index=True)
    p["date"] = p["date"].astype(str)
    p = p.drop_duplicates("date", keep="last")
    p["date"] = pd.to_datetime(p["date"])
    p = p[(p["close"] > 0) & (p["date"] <= END)].sort_values("date")
    return p.set_index("date")


def load_div(sid: str):
    """拼接該代號所有結束日 ≤2024-12-31 的股利快取檔；回傳 (現金股利, 股票股利, 覆蓋區間)。
    覆蓋區間取檔名起訖的聯集外框（區間中間若有缺檔不另偵測，列為已知限制）。"""
    parts, lo, hi = [], None, None
    for f in RAW.glob(f"TaiwanStockDividend__{sid}__*.parquet"):
        _, _, a, b = f.stem.split("__")
        if b == "latest" or b > END:
            continue
        try:
            parts.append(pd.read_parquet(f))
        except Exception as e:  # 空檔／壞檔：略過，不影響其他檔
            print(f"[警告] 讀不到 {f.name}：{type(e).__name__}")
            continue
        lo = a if lo is None or a < lo else lo
        hi = b if hi is None or b > hi else hi
    if not parts:
        return None
    d = pd.concat(parts, ignore_index=True)
    out, sx = set(), set()
    for _, r in d.iterrows():
        ann = r.get("AnnouncementDate")
        ann = pd.Timestamp(ann) if ann else None
        cash = float(r.get("CashEarningsDistribution") or 0) + float(r.get("CashStatutorySurplus") or 0)
        ex = r.get("CashExDividendTradingDate")
        if cash > 0 and ex:
            out.add((pd.Timestamp(ex), ann, cash))
        st = float(r.get("StockEarningsDistribution") or 0) + float(r.get("StockStatutorySurplus") or 0)
        ex = r.get("StockExDividendTradingDate")
        if st > 0 and ex:
            sx.add((pd.Timestamp(ex), ann))
    return sorted(out, key=str), sorted(sx, key=str), (pd.Timestamp(lo), pd.Timestamp(hi))


def price_match(code, fut, spots_all):
    """名冊沒有的舊契約：近月有成交日的 期貨收盤/現貨收盤 中位數最接近 1 者。"""
    s = fut[(fut["code"] == code) & (fut["vol"] > 0) & fut["close"].notna()]
    s = s.sort_values(["date", "ym"]).groupby("date").first()["close"]
    if len(s) < 20:
        return None, None
    s = s.iloc[:: max(1, len(s) // 40)]
    W = spots_all.reindex(s.index)  # spots_all：寬表（日期 × 代號）
    ok = W.notna().sum() >= 0.8 * len(s)
    dev = (W.loc[:, ok].rdiv(s, axis=0) - 1).abs().median()
    best = sorted((float(v), k) for k, v in dev.items())
    best.sort()
    if not best or best[0][0] > 0.02 or (len(best) > 1 and best[1][0] < 2 * best[0][0]):
        return None, best[:2]
    return best[0][1], best[:2]


def build(verbose=True):
    reg, mini = load_registry()
    fut = load_futures()
    assert_no_holdout_leakage(fut, date_col="date", context="stock_futures_basis futures")
    codes = sorted(set(fut["code"]))
    non_stock = {"TXF", "MTF", "TEF", "TFF", "XIF", "GTF", "T5F", "TJF", "GDF", "TGF", "RHF", "RTF", "BTF",
                 "E4F", "SOF", "SHF", "SXF", "UDF", "SPF", "UNF", "F1F", "G2F", "TMF", "UJF", "UAF", "UEF",
                 "XAF", "XBF", "XEF", "XJF", "BRF", "NYF", "XUF", "MXF", "CPF", "GBF", "TGF", "ZEF", "ZFF"}
    mapping, unmatched, ambiguous = {}, [], {}
    for c in codes:
        if c in mini or c in non_stock:
            continue
        if c in reg:
            mapping[c] = reg[c]
    rest = [c for c in codes if c not in mapping and c not in mini and c not in non_stock]
    if rest:
        spots_all = {}
        for f in RAW.glob("TaiwanStockPrice__*__2010-01-01__2024-12-31.parquet"):
            sid = f.name.split("__")[1]
            if len(sid) == 4 and sid.isdigit() and not sid.startswith("00"):
                try:
                    p = pd.read_parquet(f, columns=["date", "close"])
                except Exception as e:  # 空檔／壞檔：略過該檔，不影響其他比對
                    print(f"[警告] 讀不到 {f.name}：{type(e).__name__}")
                    continue
                p["date"] = pd.to_datetime(p["date"])
                spots_all[sid] = p[p["close"] > 0].drop_duplicates("date").set_index("date")["close"]
        spots_all = pd.DataFrame(spots_all)
        for c in rest:
            sid, top = price_match(c, fut, spots_all)
            if sid:
                mapping[c] = sid
            else:
                unmatched.append(c)
                ambiguous[c] = top
    # 同一標的多個代號（小型等）：保留最早出現者
    first = fut.groupby("code")["date"].min()
    by_sid = collections.defaultdict(list)
    for c, s in mapping.items():
        by_sid[s].append(c)
    dup_dropped = []
    for s, cs in by_sid.items():
        if len(cs) > 1:
            cs.sort(key=lambda c: first[c])
            for c in cs[1:]:
                dup_dropped.append((c, s))
                mapping.pop(c)
    fut = fut[fut["code"].isin(mapping)]
    tdays = sorted(set(fut["date"]))
    tidx = {d: i for i, d in enumerate(tdays)}
    # 各契約（code, ym）最後交易日＝資料最後一天；早於第三個週三 3 天以上＝提前消失（契約調整）
    ltd = fut.groupby(["code", "ym"])["date"].max()
    vanished = {k for k, d in ltd.items() if (pd.Timestamp(_third_wed(k[1])) - d).days > 3}
    return fut, mapping, unmatched, ambiguous, dup_dropped, tdays, tidx, ltd, vanished


def candidates(fut, mapping, tdays, tidx, ltd, vanished, spots, divs):
    """逐日逐檔近月契約的候選資訊（不含報酬；向量化）。"""
    excl = collections.Counter()
    f = fut.copy()
    f["T"] = [ltd[(c, y)] for c, y in zip(f["code"], f["ym"])]
    f = f[f["date"] < f["T"]]
    f = f.sort_values(["code", "date", "ym"]).groupby(["code", "date"], as_index=False).head(1)
    f["sid"] = f["code"].map(mapping)
    td = pd.Series(range(len(tdays)), index=pd.DatetimeIndex(tdays))
    f["i"] = td.reindex(f["date"]).values
    f["iT"] = td.reindex(f["T"]).values
    f = f[f["i"] + 1 < len(tdays)]
    f["t1"] = [tdays[int(k) + 1] for k in f["i"]]
    f["n_td"] = f["iT"] - f["i"]
    f["tau"] = (f["T"] - f["date"]).dt.days
    van = f.apply(lambda r: (r["code"], r["ym"]) in vanished, axis=1) if len(f) else []
    excl["契約提前消失（調整）"] = int(np.sum(van))
    f = f[~np.asarray(van, dtype=bool)]
    sp = pd.concat([s.reset_index().assign(sid=k) for k, s in spots.items()], ignore_index=True)
    a = sp[["sid", "date", "close"]].rename(columns={"close": "S"})
    f = f.merge(a, on=["sid", "date"], how="left")
    b = sp[["sid", "date", "close", "max", "min", "spread"]].rename(columns={"date": "t1", "close": "S1"})
    f = f.merge(b, on=["sid", "t1"], how="left")
    c = sp[["sid", "date"]].rename(columns={"date": "T"}).assign(hasT=True)
    f = f.merge(c, on=["sid", "T"], how="left")
    miss = f["S"].isna() | f["S1"].isna() | f["hasT"].isna()
    excl["現貨缺日或無快取"] = int(miss.sum())
    f = f[~miss].copy()
    f["locked"] = (f["S1"] == f["max"]) & (f["S1"] == f["min"]) & (f["spread"] > 0) & (
        f["spread"] / (f["S1"] - f["spread"]) >= 0.095)
    cov = f.apply(lambda r: r["sid"] in divs and divs[r["sid"]][2][0] <= r["date"]
                  and r["T"] <= divs[r["sid"]][2][1], axis=1) if len(f) else []
    excl["股利快取未涵蓋持有期"] = int(len(f) - np.sum(cov))
    f = f[np.asarray(cov, dtype=bool)].copy()
    Ds, stk = [], []
    for r in f[["sid", "date", "T"]].itertuples(index=False):
        divl, sx, _ = divs[r.sid]
        Ds.append(sum(cv for ex, ann, cv in divl if r.date < ex <= r.T and ann is not None and ann <= r.date))
        stk.append(any(r.date < ex <= r.T and ann is not None and ann <= r.date for ex, ann in sx))
    f["D"] = Ds
    f["stock_div_known"] = stk
    excl["已公告除權（契約將調整）"] = int(np.sum(stk))
    f = f[~f["stock_div_known"]]
    f = f.rename(columns={"date": "t", "close": "F"})
    return f.drop(columns=["max", "min", "spread", "hasT", "stock_div_known"]), excl


def main() -> int:
    mode = "--run" if "--run" in sys.argv else "--prep"
    if mode == "--run" and RESULT_OUT.exists():
        print(f"結果檔 {RESULT_OUT.name} 已存在：單發只跑一次，拒跑。")
        return 1
    fut, mapping, unmatched, ambiguous, dup_dropped, tdays, tidx, ltd, vanished = build()
    spots = {}
    divs = {}
    for sid in sorted(set(mapping.values())):
        s = load_spot(sid)
        if s is not None:
            assert_no_holdout_leakage(s.reset_index(), date_col="date", context=f"spot {sid}")
            spots[sid] = s
        dv = load_div(sid)
        if dv is not None:
            divs[sid] = dv
    cands, excl = candidates(fut, mapping, tdays, tidx, ltd, vanished, spots, divs)
    # 進場條件中與報酬無關的部分（τ、OI、成交、漲停）
    elig = cands[(cands["n_td"] >= TMIN_MAIN) & (cands["oi"] >= OI_MIN) & (cands["vol"] > 0)
                 & cands["F"].notna() & ~cands["locked"]]
    by_year = collections.Counter(int(y) for y in elig["t"].dt.year)
    prep = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "futures_rows": int(len(fut)),
        "stock_codes_mapped": len(mapping),
        "mapped_via_registry_or_price": mapping,
        "unmatched_codes": unmatched,
        "unmatched_top2": {k: v for k, v in ambiguous.items()},
        "duplicate_codes_dropped": dup_dropped,
        "underlyings_without_spot_cache": sorted(set(mapping.values()) - set(spots)),
        "underlyings_without_dividend_cache": sorted(set(mapping.values()) - set(divs)),
        "contracts_vanished_early": len(vanished),
        "candidate_rows": int(len(cands)),
        "excluded": dict(excl),
        "eligible_days_tmin10_oi100_vol_by_year": dict(sorted(by_year.items())),
        "note": "只整備資料、未計算任何錯價或報酬",
    }
    PREP_OUT.write_text(json.dumps(prep, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in prep.items() if k != "mapped_via_registry_or_price"},
                     ensure_ascii=False, indent=1, default=str))
    if mode == "--prep":
        return 0
    from stock_futures_basis_run import run_oneshot  # 單發本體（同目錄）
    return run_oneshot(fut, cands, spots, divs, tdays, tidx, RESULT_OUT)


if __name__ == "__main__":
    raise SystemExit(main())
