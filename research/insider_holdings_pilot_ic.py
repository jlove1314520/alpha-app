"""`HYPOTHESIS_QUEUE.md` #41（內部人董監持股轉讓）第1關cheap gate**之前**的
中小樣本pilot訊號存在性檢查（2026-09-06 hypothesis_queue排程接續，本輪）。

**這不是正式的第1關cheap IC gate**（正式版要走`factor_ic.py`
`run_ic_test()`同一套SAMPLE_SIZE=300/N_SHUFFLES=1000/bonferroni機制，需要
先把這個因子整合進`factors.py`），這裡只是`backfill_insider_holdings.py`
15檔x20季度pilot樣本回補完成後，用最輕量的方式檢查「季度董監持股合計變動率
是否跟下一季報酬有粗略相關」，決定值不值得投入把#41正式整合進標準管線的
工程成本——這正是`HYPOTHESIS_QUEUE.md` #41條目自己寫的「先用中小樣本抽樣
先驗第1關cheap gate訊號存在，再決定是否值得投入全量回補的工程成本」。

**事前綁定方向**：文獻（Seyhun 1986等，見#41條目「經濟理由」段落）預期內部人
淨增持（董監持股合計上升）對未來報酬是正向訊號，方向為正。

**已知限制（誠實記錄，不是正式判準）**：
1. 只用15檔股票（來自標準300檔樣本篩4位數字代碼取前15檔）x 20個季度快照，
   樣本量遠小於正式cheap gate的300檔x十年月頻。
2. 只抓「全體董監持股合計」單一彙總數字，未涵蓋經理人/大股東。
3. pct_change在同一檔股票的相鄰快照之間計算，若中間有`fetched_empty`的
   季度會跨季計算（沒有嚴格要求兩期間隔剛好一季），本輪未特別處理這個
   細節。
4. 洗牌null用「整個panel打散」而非「同一天橫斷面內打散」（15檔股票的
   橫斷面樣本太小，橫斷面內洗牌统计力太弱），是相關性存在性的粗略檢查，
   不是正式判準的等價物。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from adjust import adjusted_price_series
from mops_insider_holdings_client import load_all_cached

FORWARD_TRADING_DAYS = 63  # 約一季
N_SHUFFLES = 200
SHUFFLE_SEED = 20260906


def _year_month_to_date(year_roc: str, month: str) -> pd.Timestamp:
    year_western = int(year_roc) + 1911
    period = pd.Period(f"{year_western}-{month}", freq="M")
    return period.end_time.normalize()


def _forward_return(px: pd.DataFrame, as_of: pd.Timestamp, horizon: int) -> float | None:
    px = px.sort_values("date").reset_index(drop=True)
    dates = pd.to_datetime(px["date"])
    idx = dates.searchsorted(as_of, side="right")
    if idx >= len(px):
        return None
    fwd_idx = idx + horizon
    if fwd_idx >= len(px):
        return None
    p0 = px["adj_close"].iloc[idx]
    p1 = px["adj_close"].iloc[fwd_idx]
    if p0 is None or p1 is None or p0 <= 0:
        return None
    return float(p1 / p0 - 1.0)


def build_panel() -> pd.DataFrame:
    raw = load_all_cached()
    raw = raw[raw["typek"] == "sii"].copy()
    raw = raw.dropna(subset=["board_holdings_total"])
    raw["date"] = raw.apply(lambda r: _year_month_to_date(r["year_roc"], r["month"]), axis=1)
    raw = raw.sort_values(["stock_id", "date"]).reset_index(drop=True)

    rows = []
    price_cache: dict[str, pd.DataFrame] = {}
    for sid, g in raw.groupby("stock_id"):
        g = g.sort_values("date").reset_index(drop=True)
        g["pct_change_holdings"] = g["board_holdings_total"].pct_change()
        try:
            if sid not in price_cache:
                price_cache[sid] = adjusted_price_series(sid, "2010-01-01")
        except Exception as e:  # noqa: BLE001 -- 記錄後跳過這檔，不中斷整體pilot
            print(f"  [WARN] {sid} 價格序列載入失敗: {e}")
            continue
        px = price_cache[sid]
        if px.empty:
            print(f"  [WARN] {sid} 價格序列為空，跳過")
            continue
        for _, r in g.iloc[1:].iterrows():
            factor = r["pct_change_holdings"]
            if pd.isna(factor):
                continue
            fwd = _forward_return(px, r["date"], FORWARD_TRADING_DAYS)
            if fwd is None:
                continue
            rows.append({
                "stock_id": sid, "date": r["date"],
                "pct_change_holdings": float(factor), "fwd_return": fwd,
            })
    return pd.DataFrame(rows)


def run_pilot_check() -> dict:
    panel = build_panel()
    n = len(panel)
    n_stocks = panel["stock_id"].nunique() if n else 0
    print(f"panel: {n}筆觀測，涵蓋{n_stocks}檔股票")
    if n < 20:
        print("樣本量過小（<20），無法做有意義的相關性檢定，pilot判定：樣本不足")
        return {"n": n, "n_stocks": n_stocks, "status": "insufficient_sample"}

    r_real, p_real = spearmanr(panel["pct_change_holdings"], panel["fwd_return"])
    print(f"\n真實Spearman IC: r={r_real:+.4f}  p={p_real:.4f}  (事前綁定方向：正)")

    rng = np.random.default_rng(SHUFFLE_SEED)
    null_rs = []
    fwd_vals = panel["fwd_return"].to_numpy()
    factor_vals = panel["pct_change_holdings"].to_numpy()
    for _ in range(N_SHUFFLES):
        shuffled = rng.permutation(factor_vals)
        r_null, _ = spearmanr(shuffled, fwd_vals)
        null_rs.append(r_null)
    null_rs = np.array(null_rs)
    percentile = float((null_rs < r_real).mean() * 100)
    print(f"洗牌null分布（N={N_SHUFFLES}，整個panel打散，非橫斷面內）：percentile={percentile:.1f}")
    print("（這是粗略pilot檢查，非正式第1關判準——正式判準需整合進factor_ic.py用"
          "SAMPLE_SIZE=300/N_SHUFFLES=1000跑）")

    out = {
        "n": n, "n_stocks": n_stocks, "r_real": float(r_real), "p_real": float(p_real),
        "null_percentile": percentile, "status": "computed",
    }
    out_path = Path(__file__).parent / "data" / "insider_holdings_pilot_ic_result.csv"
    out_path.parent.mkdir(exist_ok=True)
    pd.DataFrame([out]).to_csv(out_path, index=False)
    panel.to_csv(Path(__file__).parent / "data" / "insider_holdings_pilot_panel.csv", index=False)
    return out


if __name__ == "__main__":
    run_pilot_check()
