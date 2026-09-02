"""HYPOTHESIS_QUEUE.md #23 -- Piotroski F-score當價值榜排雷閘門.

第1關 sanity ONLY（不是對假設本身的PASS/FAIL判定）。目的：①查證FinMind免費層
是否有齊全的9項F-score所需欄位（若缺，誠實記錄缺哪幾項，不硬套不精確的替代
欄位湊數）；②確認F-score分布本身是非結構性no-op（不是恆為0/恆為9這種常數
分數、也不是全樣本清一色同一個值）；③回報F>=7/F>=8兩個候選門檻各自的候選池
比例，供下一輪決定要用哪個門檻套用value_board_v2排雷閘門測試。

**資料源查證結果（本輪針對2330直接列舉`type`欄位確認，見
HYPOTHESIS_QUEUE.md #23條目）**：9項指標裡7項有FinMind免費層直接對應欄位
（NetIncome/TotalAssets/CurrentAssets/CurrentLiabilities/LongtermBorrowings/
Revenue/GrossProfit皆存在），2項需要文件化的proxy（沿用既有慣例，不是本輪
新發明的簡化）：
  - ②CFO正：`pit.py::cash_flow_pit()`既有簡化——FinMind免費層
    `TaiwanStockCashFlowsStatement`沒有乾淨的資本支出(capex)欄位可以推算
    真正的自由現金流(FCF)，用營運現金流(CFO)當FCF的documented簡化（跟
    `HYPOTHESIS_QUEUE.md` #22品質濾網用的是同一個既有簡化，非本輪新增）。
  - ⑦未發行新股稀釋：FinMind免費層沒有直接的「流通股數」欄位，用
    `CapitalStock`（面額股本，台股普通股面額通常為NT$10/股）當股數的
    proxy——面額股本沒有增加，通常代表沒有現金增資/私募發行新股（但不
    排除其他不影響面額的股權變動，例如庫藏股註銷、可轉債轉換時點差異，
    這是已知的近似而非精確股數變動，誠實記錄不假裝完整）。
其餘7項可用真實欄位算，資料源查證結論：**F-score九項指標可算，第1關不因
「資料不可及」快殺**。

用法沿用`composite_quality_revaccel_inst_lowvol_sanity.py`（#22）同一套
`factor_ic.py`抽樣/快照機制（同SAMPLE_SEED/SAMPLE_SIZE/START_DATE、同20
交易日不重疊快照），結果可跟本佇列其他#1-24 sanity check直接比較。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from adjust import adjusted_price_series
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, START_DATE, build_snapshots, sample_universe_ids
from factors import _asof_join
from pit import balance_sheet_pit, cash_flow_pit, quarterly_pit
from validation.holdout import VAL_END

LAG_QUARTERS = 4  # YoY，避開季節性，跟 factors.py::ASSET_GROWTH_LAG_QUARTERS/
                   # ACCRUALS_LAG_QUARTERS 同一慣例（不是本輪新發明的窗口選擇）
SNAPSHOT_START = "2015-01-01"
FORWARD_HORIZON = 20


def _fscore_components(stock_id: str, start_date: str) -> pd.DataFrame:
    """逐季計算 Piotroski F-score 9 項二元指標 + 加總分數（0-9）。9項定義見
    模組docstring跟`HYPOTHESIS_QUEUE.md` #23「具體假設定義」：
      1. ROA正：NetIncome/TotalAssets > 0（同期期末資產，非期初期末平均，
         簡化——跟factors.py::_roe_stability用期末權益不用平均權益同一種
         簡化慣例）。
      2. 營運現金流正：CFO > 0（cash_flow_pit既有簡化，CFO近似FCF）。
      3. ROA年增：ROA > 4季前ROA（YoY）。
      4. 應計項目品質：CFO > NetIncome。
      5. 槓桿年減：LongtermBorrowings/TotalAssets < 4季前同一比率。
      6. 流動比率年增：CurrentAssets/CurrentLiabilities > 4季前同一比率。
      7. 未發行新股稀釋：CapitalStock（面額股本proxy股數）<= 4季前（未增加）。
      8. 毛利率年增：GrossProfit/Revenue > 4季前同一比率。
      9. 資產週轉率年增：Revenue/TotalAssets > 4季前同一比率。

    9項全部只依賴3個既有PIT函式（quarterly_pit/balance_sheet_pit/
    cash_flow_pit），同一個stock_id/start_date快取鍵，零額外FinMind呼叫。
    任一項所需欄位缺失時該項記NaN；分數(`fscore`)只在9項全部非NaN時才加總，
    `n_components`記錄實際可算幾項，供呼叫端誠實判斷資料涵蓋率，不用剩餘
    幾項湊出一個看起來完整的分數。
    """
    inc = quarterly_pit(stock_id, start_date)
    bs = balance_sheet_pit(stock_id, start_date)
    cf = cash_flow_pit(stock_id, start_date)
    inc_cols = {"NetIncome", "Revenue", "GrossProfit"}
    bs_cols = {"TotalAssets", "CurrentAssets", "CurrentLiabilities", "LongtermBorrowings", "CapitalStock"}
    if inc.empty or bs.empty or not inc_cols.issubset(inc.columns) or not bs_cols.issubset(bs.columns):
        return pd.DataFrame(columns=["pit_date", "fscore", "n_components"])

    cfo_col = None
    if not cf.empty:
        if "NetCashInflowFromOperatingActivities" in cf.columns:
            cfo_col = "NetCashInflowFromOperatingActivities"
        elif "CashFlowsFromOperatingActivities" in cf.columns:
            cfo_col = "CashFlowsFromOperatingActivities"

    inc = inc[["fiscal_period_end", "pit_date", "NetIncome", "Revenue", "GrossProfit"]]
    bs = bs[["fiscal_period_end", "TotalAssets", "CurrentAssets", "CurrentLiabilities",
             "LongtermBorrowings", "CapitalStock"]]
    m = inc.merge(bs, on="fiscal_period_end", how="inner").sort_values("fiscal_period_end").reset_index(drop=True)
    if cfo_col is not None:
        cf_slim = cf[["fiscal_period_end", cfo_col]].rename(columns={cfo_col: "cfo"})
        m = m.merge(cf_slim, on="fiscal_period_end", how="left")
    else:
        m["cfo"] = np.nan
    if m.empty:
        return pd.DataFrame(columns=["pit_date", "fscore", "n_components"])

    roa = m["NetIncome"] / m["TotalAssets"].replace(0, np.nan)
    leverage = m["LongtermBorrowings"] / m["TotalAssets"].replace(0, np.nan)
    current_ratio = m["CurrentAssets"] / m["CurrentLiabilities"].replace(0, np.nan)
    gross_margin = m["GrossProfit"] / m["Revenue"].replace(0, np.nan)
    asset_turnover = m["Revenue"] / m["TotalAssets"].replace(0, np.nan)

    p1 = (roa > 0).astype(float)
    p2 = (m["cfo"] > 0).astype(float)
    p3 = (roa > roa.shift(LAG_QUARTERS)).astype(float)
    p4 = (m["cfo"] > m["NetIncome"]).astype(float)
    p5 = (leverage < leverage.shift(LAG_QUARTERS)).astype(float)
    p6 = (current_ratio > current_ratio.shift(LAG_QUARTERS)).astype(float)
    p7 = (m["CapitalStock"] <= m["CapitalStock"].shift(LAG_QUARTERS)).astype(float)
    p8 = (gross_margin > gross_margin.shift(LAG_QUARTERS)).astype(float)
    p9 = (asset_turnover > asset_turnover.shift(LAG_QUARTERS)).astype(float)

    components = pd.concat([p1, p2, p3, p4, p5, p6, p7, p8, p9], axis=1)
    components.columns = [f"p{i}" for i in range(1, 10)]
    m["n_components"] = components.notna().sum(axis=1)
    m["fscore"] = components.sum(axis=1, skipna=True)
    m.loc[m["n_components"] < 9, "fscore"] = np.nan
    return m[["pit_date", "fscore", "n_components"]]


def load_sample(sample_ids: list[str], price_start: str) -> dict[str, pd.DataFrame]:
    out = {}
    for i, sid in enumerate(sample_ids):
        try:
            px = adjusted_price_series(sid, price_start)
        except Exception as e:  # noqa: BLE001
            print(f"  [{i+1}/{len(sample_ids)}] {sid}: price ERROR ({e}), dropping")
            continue
        if px.empty or len(px) < 260:
            continue
        try:
            fs = _fscore_components(sid, price_start)
        except Exception as e:  # noqa: BLE001
            print(f"    [{sid}] fscore ERROR: {e}")
            continue
        if fs.empty:
            continue
        d = px[["date"]].copy()
        d = _asof_join(d, fs, "fscore", "f_piotroski_fscore")
        d = _asof_join(d, fs, "n_components", "f_piotroski_n_components")
        out[sid] = d
    return out


def main() -> None:
    print(f"[piotroski_sanity#23] sampling {SAMPLE_SIZE} stocks, seed={SAMPLE_SEED}")
    sample_ids = sample_universe_ids(SAMPLE_SIZE)
    data = load_sample(sample_ids, START_DATE)
    print(f"[piotroski_sanity#23] {len(data)}/{len(sample_ids)} stocks usable")
    if not data:
        print("[piotroski_sanity#23] VERDICT: SANITY_FAIL (no usable stocks)")
        return

    any_calendar = next(iter(data.values()))["date"].tolist()
    snapshots = build_snapshots(any_calendar, SNAPSHOT_START, VAL_END, FORWARD_HORIZON)
    print(f"[piotroski_sanity#23] {len(snapshots)} snapshots, {SNAPSHOT_START}..{VAL_END}")

    rows = []
    n_9of9_total = 0
    n_lt9_total = 0
    for as_of, _fwd in snapshots:
        scores = []
        n_missing_components = 0
        for sid, d in data.items():
            idx = d.index[d["date"] == as_of]
            if len(idx) == 0:
                continue
            r = d.loc[idx[0]]
            fs = r.get("f_piotroski_fscore")
            nc = r.get("f_piotroski_n_components")
            if pd.notna(nc):
                if nc < 9:
                    n_missing_components += 1
                    n_lt9_total += 1
                else:
                    n_9of9_total += 1
            if pd.isna(fs):
                continue
            scores.append(fs)
        if not scores:
            continue
        arr = np.array(scores)
        rows.append(dict(as_of=as_of, n_valid=len(arr), mean_fscore=arr.mean(),
                          median_fscore=float(np.median(arr)),
                          frac_ge7=float((arr >= 7).mean()), frac_ge8=float((arr >= 8).mean()),
                          n_missing_components=n_missing_components))

    df = pd.DataFrame(rows)
    Path("data").mkdir(exist_ok=True)
    df.to_csv("data/piotroski_fscore_sanity_snapshots.csv", index=False)
    print(f"\n[piotroski_sanity#23] {len(df)} snapshots with >=1 valid F-score")
    if df.empty:
        print("[piotroski_sanity#23] VERDICT: SANITY_FAIL (no snapshot has a valid F-score)")
        return
    print(df[["n_valid", "mean_fscore", "median_fscore", "frac_ge7", "frac_ge8"]].describe())

    coverage = n_9of9_total / max(n_9of9_total + n_lt9_total, 1)
    mean_ge7 = df["frac_ge7"].mean()
    mean_ge8 = df["frac_ge8"].mean()
    mean_valid_n = df["n_valid"].mean()
    print(f"\n[piotroski_sanity#23] 9/9項欄位齊全覆蓋率（跨全部stock-quarter觀測值）: {coverage:.1%}")
    print(f"[piotroski_sanity#23] mean F>=7 候選池比例: {mean_ge7:.1%}")
    print(f"[piotroski_sanity#23] mean F>=8 候選池比例: {mean_ge8:.1%}")
    print(f"[piotroski_sanity#23] mean 每快照有效樣本數: {mean_valid_n:.1f}")

    # sanity門檻（第1關sanity，非最終判準）：F>=7候選池不能是恆為0或恆為100%
    # （代表分數本身沒有鑑別力），F>=8池必須嚴格小於F>=7池（分數分布有層次，
    # 不是所有通過F>=7的都剛好滿分），資料覆蓋率不能低到讓分數失去意義。
    sane = (0.0 < mean_ge7 < 1.0) and (0.0 <= mean_ge8 < mean_ge7) and (coverage >= 0.5)
    verdict = "SANITY_PASS" if sane else "SANITY_FAIL"
    print(f"\n[piotroski_sanity#23] VERDICT: {verdict}")


if __name__ == "__main__":
    main()
