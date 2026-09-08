"""`HYPOTHESIS_QUEUE.md` #58 反向波動度加權投資組合建構
Inverse-Volatility-Weighted Portfolio Construction 第1關 sanity。

**這輪只做sanity，不做判定**：依`HYPOTHESIS_QUEUE_PROTOCOL.md`「這一輪先把
地基做好」原則——確認加權後組合報酬序列非退化（無NaN/Inf）、再平衡確實有
觸發、且最基本的前提成立：**反向波動度加權後的組合波動度確實低於等權重
buy-and-hold版本**（這是這個構造的必要前提，若不成立代表實作有bug，不談
訊號）。不強求本輪判定PASS/FAIL，留給第2關以後。

**跟#29共用同一批宇宙/基準操作化，理由沿用`equal_weight_rebalance_sanity.py`
docstring已寫明的原因，這裡不重複展開**：專案沒有市值/流通股數資料源，基準
改用「同一組標的、t0等權重起跑、之後永不主動調整（純buy-and-hold）」而非
市值加權。本腳本刻意獨立複製`load_prices`/`build_panel`邏輯而非import
`equal_weight_rebalance_sanity.py`，維持「每支假設腳本可獨立重跑」的既有慣例
（`equal_weight_rebalance_sanity.py`docstring已說明的同一個理由）。

**加權公式（事前綁定，見`HYPOTHESIS_QUEUE.md`#58條目「具體假設定義」）**：
`w_{i,t} = (1/sigma_{i,t}) / sum_j(1/sigma_{j,t})`，`sigma_{i,t}`為trailing
60個交易日日報酬標準差。每`REBAL_FREQ`（21交易日，跟#29同一個月頻換股慣例）
交易日，用當時的trailing 60日波動度重新計算權重並再平衡；兩次再平衡之間，
權重隨個股報酬自然漂移（跟#29`simulate()`的`w_rebal`漂移邏輯相同機制，只是
拉回目標從「等權重」換成「當時算出的反向波動度權重」）。

2026-09-08 由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程新增，佇列#58第1關
sanity起跑。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from adjust import adjusted_price_series
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, SNAPSHOT_START, START_DATE, sample_universe_ids
from validation import holdout

REBAL_FREQ = 21  # trading days, ~monthly，跟#29/dividend_yield_portfolio_v1同一個月頻慣例
VOL_WINDOW = 60  # trailing daily-return std window，跟#53/#57已用過的常見窗口一致，非新選點
MIN_HISTORY_DAYS = 500  # 跟#29 equal_weight_rebalance_sanity.py同一個門檻
WINDOW_START = SNAPSHOT_START  # 2015-01-01，跟#29同一個起點，方便跨假設比較
WINDOW_END = holdout.VAL_END


def load_prices(sample_ids: list[str]) -> dict[str, pd.Series]:
    """回傳 stock_id -> date-indexed adj_close Series，capped at VAL_END。
    獨立複製自`equal_weight_rebalance_sanity.py`，理由見上方模組docstring。"""
    out = {}
    for i, sid in enumerate(sample_ids):
        try:
            px = adjusted_price_series(sid, START_DATE)
        except Exception as e:  # noqa: BLE001
            print(f"  [{i+1}/{len(sample_ids)}] {sid}: price ERROR ({e}), dropping")
            continue
        if px.empty:
            continue
        s = px.set_index("date")["adj_close"].dropna()
        s = s[s > 0]
        if len(s) >= MIN_HISTORY_DAYS:
            out[sid] = s
    return out


def build_panel(prices: dict[str, pd.Series]) -> pd.DataFrame:
    """跟#29 equal_weight_rebalance_sanity.py::build_panel完全相同的邏輯
    （同一個宇宙+同一個視窗+同一套存活者偏差篩選規則），確保panel跟#29一致，
    才是真正共用「同一批159檔」而不是巧合湊出類似數字。"""
    df = pd.DataFrame(prices)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    df = df[(df.index >= pd.Timestamp(WINDOW_START)) & (df.index <= pd.Timestamp(WINDOW_END))]
    valid_cols = [
        c for c in df.columns
        if df[c].first_valid_index() is not None
        and df[c].first_valid_index() <= df.index[5]
        and df[c].last_valid_index() >= df.index[-5]
    ]
    df = df[valid_cols]
    df = df.ffill(limit=5).bfill(limit=5)
    df = df.dropna(axis=1)
    return df


def simulate(panel: pd.DataFrame, rebal_freq: int, vol_window: int) -> pd.DataFrame:
    """回傳index=交易日、欄位buyhold_ret/invvol_ret（當日報酬率，非累積）的
    DataFrame，attrs紀錄再平衡事件數與每次拉回前的權重離散度。

    buyhold：t0等權重起跑，之後永不主動調整（跟#29同一個基準）。
    invvol：t0等權重起跑（因為t0之前沒有trailing 60日資料可算波動度），
    自第一個滿足`vol_window`交易日的再平衡點起改用反向波動度權重拉回，
    之後每次再平衡都用當時的trailing窗口重新計算。
    """
    rets = panel.pct_change().dropna(how="all")
    rets = rets.fillna(0.0)  # 防禦性補0——經build_panel清理後理論上不應再有NaN
    n = panel.shape[1]
    w_buyhold = np.full(n, 1.0 / n)
    w_invvol = np.full(n, 1.0 / n)
    buyhold_rets, invvol_rets, dispersions = [], [], []
    rebal_events = 0
    ret_values = rets.values
    for t in range(ret_values.shape[0]):
        r = ret_values[t]
        port_ret_bh = float(np.dot(w_buyhold, r))
        buyhold_rets.append(port_ret_bh)
        w_buyhold = w_buyhold * (1 + r)
        w_buyhold = w_buyhold / w_buyhold.sum()

        port_ret_iv = float(np.dot(w_invvol, r))
        invvol_rets.append(port_ret_iv)
        w_invvol = w_invvol * (1 + r)
        w_invvol = w_invvol / w_invvol.sum()

        if (t + 1) % rebal_freq == 0 and t + 1 >= vol_window:
            window = ret_values[t + 1 - vol_window : t + 1]
            sigma = window.std(axis=0, ddof=1)
            sigma = np.where(sigma > 0, sigma, np.nan)
            inv_sigma = 1.0 / sigma
            if np.all(np.isnan(inv_sigma)):
                # 防禦性：理論上不應發生（build_panel已篩掉全歷史缺口股票），
                # 若真的碰到則保留現有權重不動，不製造除以0
                continue
            inv_sigma = np.nan_to_num(inv_sigma, nan=0.0)
            new_w = inv_sigma / inv_sigma.sum()
            dispersions.append(float(np.std(new_w)))
            w_invvol = new_w
            rebal_events += 1

    out = pd.DataFrame({"buyhold_ret": buyhold_rets, "invvol_ret": invvol_rets}, index=rets.index)
    out.attrs["rebal_events"] = rebal_events
    out.attrs["post_rebal_weight_dispersion_mean"] = (
        float(np.mean(dispersions)) if dispersions else float("nan")
    )
    return out


def summarize(ret_series: pd.Series) -> dict:
    cum = (1 + ret_series).cumprod()
    total_return = float(cum.iloc[-1] - 1)
    ann_vol = float(ret_series.std() * np.sqrt(252))
    sharpe = float(ret_series.mean() / ret_series.std() * np.sqrt(252)) if ret_series.std() > 0 else float("nan")
    running_max = cum.cummax()
    mdd = float((cum / running_max - 1).min())
    return {"total_return": total_return, "ann_vol": ann_vol, "sharpe": sharpe, "mdd": mdd}


def main():
    assert holdout.is_holdout_consumed() is False, "holdout已消耗，禁止繼續（協定第3節第1項）"

    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    print(f"樣本：{len(sample_ids)}檔(SEED={SAMPLE_SEED})，跟#29/#11/#17/#28共用同一個300檔宇宙")
    prices = load_prices(sample_ids)
    print(f"  {len(prices)}/{len(sample_ids)}檔通過最低歷史長度門檻({MIN_HISTORY_DAYS}交易日)")

    panel = build_panel(prices)
    print(f"最終panel：{panel.shape[1]}檔股票 x {panel.shape[0]}個交易日"
          f"（{panel.index[0].date()}..{panel.index[-1].date()}），"
          f"視窗頭尾涵蓋度篩選(存活者偏差，見docstring)")

    if panel.shape[1] < 30:
        print(f"SANITY FAIL: 可用股票數({panel.shape[1]})過少，判結構性不可靠，不繼續")
        return

    sim = simulate(panel, REBAL_FREQ, VOL_WINDOW)
    print(f"\n再平衡事件數：{sim.attrs['rebal_events']}次（{REBAL_FREQ}交易日一次，"
          f"需累積滿{VOL_WINDOW}日才開始算波動度，前面幾次再平衡點理論上會被跳過）")
    print(f"每次拉回後的權重離散度(std)平均：{sim.attrs['post_rebal_weight_dispersion_mean']:.5f}"
          f"（>0代表各股波動度確實不同、拉回動作不是no-op；若接近0代表個股波動度"
          f"幾乎完全相同，加權跟等權重沒有實質差異，需要另外檢查資料是否有問題）")

    nan_check = int(sim.isna().sum().sum())
    inf_check = int(np.isinf(sim.values).sum())
    print(f"\n報酬序列NaN檢查：{nan_check}（應為0）  Inf檢查：{inf_check}（應為0）")

    periods = [
        (f"TRAIN({WINDOW_START}..{holdout.TRAIN_END})", sim.index <= pd.Timestamp(holdout.TRAIN_END)),
        (f"VAL({holdout.TRAIN_END}..{holdout.VAL_END})", sim.index > pd.Timestamp(holdout.TRAIN_END)),
        (f"FULL({WINDOW_START}..{holdout.VAL_END})", pd.Series(True, index=sim.index)),
    ]
    vol_ratio_all_below_1 = True
    for period_label, mask in periods:
        sub = sim[mask]
        bh = summarize(sub["buyhold_ret"])
        iv = summarize(sub["invvol_ret"])
        vol_ratio = iv["ann_vol"] / bh["ann_vol"] if bh["ann_vol"] > 0 else float("nan")
        if not (vol_ratio < 1.0):
            vol_ratio_all_below_1 = False
        print(f"\n=== {period_label} ({len(sub)}個交易日) ===")
        print(f"  buyhold(等權起始,不再平衡):       total_return={bh['total_return']:+.2%}  "
              f"ann_vol={bh['ann_vol']:.2%}  sharpe={bh['sharpe']:+.3f}  mdd={bh['mdd']:.2%}")
        print(f"  invvol(每{REBAL_FREQ}日拉回反向波動度權重): total_return={iv['total_return']:+.2%}  "
              f"ann_vol={iv['ann_vol']:.2%}  sharpe={iv['sharpe']:+.3f}  mdd={iv['mdd']:.2%}")
        print(f"  波動度比值(invvol/buyhold)：{vol_ratio:.4f}"
              f"（sanity基本前提：必須<1.0，代表加權後組合波動度確實低於等權重版本；"
              f"此輪僅sanity方向檢查，不是最終判定——第2關以後才會用隨機控制組"
              f"跟alpha顯著性正式判定）")

    print(f"\n=== SANITY基本前提檢查 ===")
    print(f"三個期間(TRAIN/VAL/FULL)波動度比值皆<1.0："
          f"{'PASS' if vol_ratio_all_below_1 else 'FAIL——實作可能有bug，需先抓出bug再談訊號'}")

    assert holdout.is_holdout_consumed() is False, "holdout已消耗，禁止繼續（協定第3節第1項）"

    out_path = Path(__file__).parent / "data" / "inverse_vol_weighted_portfolio_gate58_daily_returns.csv"
    sim.to_csv(out_path)
    print(f"\n逐日報酬序列已存 {out_path.relative_to(Path(__file__).parent)}"
          f"（gitignored，供下一輪接續分析用）")


if __name__ == "__main__":
    main()
