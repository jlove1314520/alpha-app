"""`HYPOTHESIS_QUEUE.md` #59 最小變異數投資組合建構
Minimum-Variance Portfolio Construction（共變異數矩陣版）第1關 sanity。

**這輪只做sanity，不做判定**：依`HYPOTHESIS_QUEUE_PROTOCOL.md`「這一輪先把
地基做好」原則——確認加權後組合報酬序列非退化（無NaN/Inf）、再平衡確實有
觸發、且最基本的前提成立：**最小變異數加權後的組合波動度應低於等權重
buy-and-hold版本**（這是這個構造的必要前提，若不成立代表實作有bug，不談
訊號）。額外跟`#58`（反向波動度加權，忽略共變異數）並列比較，因為兩者
共用同一批宇宙/同一個基準，理論上最小變異數應該不劣於（甚至優於）反向
波動度版本——若明顯更差，代表Ledoit-Wolf收縮或負權重裁剪的實作可能有問題。

**跟#29/#58共用同一批宇宙/基準操作化，理由沿用`equal_weight_rebalance_
sanity.py`/`inverse_vol_weighted_portfolio_gate58.py`docstring已寫明的
原因，這裡不重複展開**。本腳本刻意獨立複製`load_prices`/`build_panel`
邏輯而非import其他假設腳本，維持「每支假設腳本可獨立重跑」的既有慣例。

**權重公式（事前綁定，見`HYPOTHESIS_QUEUE.md`#59條目「具體假設定義」）**：
`w* = Sigma^-1 . 1 / (1' . Sigma^-1 . 1)`，`Sigma`為trailing 60個交易日
日報酬的Ledoit-Wolf收縮共變異數估計（60個觀測值<159檔股票，樣本共變異數
矩陣奇異無法求逆，收縮估計是解決n<p問題的標準做法，非本次自創）。
負權重裁剪為0後重新正規化（long-only近似，事前寫死非事後挑選）。每
`REBAL_FREQ`（21交易日，跟#29/#58同一個月頻慣例）交易日重新估計並拉回。

2026-09-08 馬拉松第445輪（TW軌）新增，佇列#59第1關sanity起跑。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf

from adjust import adjusted_price_series
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, SNAPSHOT_START, START_DATE, sample_universe_ids
from validation import holdout

REBAL_FREQ = 21  # trading days, ~monthly，跟#29/#58同一個月頻慣例
COV_WINDOW = 60  # trailing daily-return window，跟#58的VOL_WINDOW一致，非新選點
MIN_HISTORY_DAYS = 500  # 跟#29/#58同一個門檻
WINDOW_START = SNAPSHOT_START  # 2015-01-01，跟#29/#58同一個起點，方便跨假設比較
WINDOW_END = holdout.VAL_END


def load_prices(sample_ids: list[str]) -> dict[str, pd.Series]:
    """回傳 stock_id -> date-indexed adj_close Series，capped at VAL_END。
    獨立複製自`inverse_vol_weighted_portfolio_gate58.py`，理由見上方模組docstring。"""
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
    """跟#29/#58 build_panel完全相同的邏輯（同一個宇宙+同一個視窗+同一套
    存活者偏差篩選規則），確保panel跟#29/#58一致，才是真正共用「同一批
    159檔」而不是巧合湊出類似數字。"""
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


def min_variance_weights(window: np.ndarray) -> np.ndarray:
    """給定 (COV_WINDOW x n) 的日報酬矩陣，回傳long-only近似的全域最小
    變異數權重。Ledoit-Wolf收縮估計共變異數矩陣（處理n<p奇異問題），
    封閉解 w=Sigma^-1.1/(1'.Sigma^-1.1)，負權重裁剪為0後重新正規化。"""
    lw = LedoitWolf().fit(window)
    sigma = lw.covariance_
    n = sigma.shape[0]
    ones = np.ones(n)
    try:
        inv_sigma_ones = np.linalg.solve(sigma, ones)
    except np.linalg.LinAlgError:
        # 防禦性：Ledoit-Wolf收縮理論上應保證正定可逆，若仍失敗則退回等權重
        return ones / n
    denom = float(ones @ inv_sigma_ones)
    w = inv_sigma_ones / denom
    w = np.clip(w, 0.0, None)
    total = w.sum()
    if total <= 0:
        return ones / n
    return w / total


def simulate(panel: pd.DataFrame, rebal_freq: int, cov_window: int) -> pd.DataFrame:
    """回傳index=交易日、欄位buyhold_ret/minvar_ret（當日報酬率，非累積）的
    DataFrame，attrs紀錄再平衡事件數與每次拉回前的權重離散度/有效持股數。

    buyhold：t0等權重起跑，之後永不主動調整（跟#29/#58同一個基準）。
    minvar：t0等權重起跑（t0之前沒有trailing 60日資料可估共變異數），自第
    一個滿足`cov_window`交易日的再平衡點起改用最小變異數權重拉回，之後每次
    再平衡都用當時的trailing窗口重新估計。
    """
    rets = panel.pct_change().dropna(how="all")
    rets = rets.fillna(0.0)  # 防禦性補0——經build_panel清理後理論上不應再有NaN
    n = panel.shape[1]
    w_buyhold = np.full(n, 1.0 / n)
    w_minvar = np.full(n, 1.0 / n)
    buyhold_rets, minvar_rets, dispersions, eff_n_list = [], [], [], []
    rebal_events = 0
    ret_values = rets.values
    for t in range(ret_values.shape[0]):
        r = ret_values[t]
        port_ret_bh = float(np.dot(w_buyhold, r))
        buyhold_rets.append(port_ret_bh)
        w_buyhold = w_buyhold * (1 + r)
        w_buyhold = w_buyhold / w_buyhold.sum()

        port_ret_mv = float(np.dot(w_minvar, r))
        minvar_rets.append(port_ret_mv)
        w_minvar = w_minvar * (1 + r)
        w_minvar = w_minvar / w_minvar.sum()

        if (t + 1) % rebal_freq == 0 and t + 1 >= cov_window:
            window = ret_values[t + 1 - cov_window : t + 1]
            new_w = min_variance_weights(window)
            dispersions.append(float(np.std(new_w)))
            # 有效持股數（inverse Herfindahl），衡量集中度：越接近n代表越分散
            eff_n_list.append(float(1.0 / np.sum(new_w ** 2)))
            w_minvar = new_w
            rebal_events += 1

    out = pd.DataFrame({"buyhold_ret": buyhold_rets, "minvar_ret": minvar_rets}, index=rets.index)
    out.attrs["rebal_events"] = rebal_events
    out.attrs["post_rebal_weight_dispersion_mean"] = (
        float(np.mean(dispersions)) if dispersions else float("nan")
    )
    out.attrs["post_rebal_effective_n_mean"] = (
        float(np.mean(eff_n_list)) if eff_n_list else float("nan")
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
    print(f"樣本：{len(sample_ids)}檔(SEED={SAMPLE_SEED})，跟#29/#58共用同一個300檔宇宙")
    prices = load_prices(sample_ids)
    print(f"  {len(prices)}/{len(sample_ids)}檔通過最低歷史長度門檻({MIN_HISTORY_DAYS}交易日)")

    panel = build_panel(prices)
    print(f"最終panel：{panel.shape[1]}檔股票 x {panel.shape[0]}個交易日"
          f"（{panel.index[0].date()}..{panel.index[-1].date()}），"
          f"視窗頭尾涵蓋度篩選(存活者偏差，見docstring)")

    if panel.shape[1] < 30:
        print(f"SANITY FAIL: 可用股票數({panel.shape[1]})過少，判結構性不可靠，不繼續")
        return

    sim = simulate(panel, REBAL_FREQ, COV_WINDOW)
    print(f"\n再平衡事件數：{sim.attrs['rebal_events']}次（{REBAL_FREQ}交易日一次，"
          f"需累積滿{COV_WINDOW}日才開始估共變異數，前面幾次再平衡點理論上會被跳過）")
    print(f"每次拉回後的權重離散度(std)平均：{sim.attrs['post_rebal_weight_dispersion_mean']:.5f}"
          f"（>0代表最小變異數解確實有差異化配置、不是no-op）")
    print(f"每次拉回後的有效持股數(1/HHI)平均：{sim.attrs['post_rebal_effective_n_mean']:.1f}"
          f"（滿分{panel.shape[1]}＝完全等權重；若接近0代表解退化成集中在極少數股票，"
          f"需要檢查Ledoit-Wolf收縮或負權重裁剪是否有問題）")

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
        mv = summarize(sub["minvar_ret"])
        vol_ratio = mv["ann_vol"] / bh["ann_vol"] if bh["ann_vol"] > 0 else float("nan")
        if not (vol_ratio < 1.0):
            vol_ratio_all_below_1 = False
        print(f"\n=== {period_label} ({len(sub)}個交易日) ===")
        print(f"  buyhold(等權起始,不再平衡):         total_return={bh['total_return']:+.2%}  "
              f"ann_vol={bh['ann_vol']:.2%}  sharpe={bh['sharpe']:+.3f}  mdd={bh['mdd']:.2%}")
        print(f"  minvar(每{REBAL_FREQ}日拉回最小變異數權重): total_return={mv['total_return']:+.2%}  "
              f"ann_vol={mv['ann_vol']:.2%}  sharpe={mv['sharpe']:+.3f}  mdd={mv['mdd']:.2%}")
        print(f"  波動度比值(minvar/buyhold)：{vol_ratio:.4f}"
              f"（sanity基本前提：必須<1.0，代表加權後組合波動度確實低於等權重版本；"
              f"此輪僅sanity方向檢查，不是最終判定——第2關以後才會用隨機控制組"
              f"跟alpha顯著性正式判定）")

    print(f"\n=== SANITY基本前提檢查 ===")
    print(f"三個期間(TRAIN/VAL/FULL)波動度比值皆<1.0："
          f"{'PASS' if vol_ratio_all_below_1 else 'FAIL——實作可能有bug，需先抓出bug再談訊號'}")

    assert holdout.is_holdout_consumed() is False, "holdout已消耗，禁止繼續（協定第3節第1項）"

    out_path = Path(__file__).parent / "data" / "min_variance_portfolio_gate59_daily_returns.csv"
    sim.to_csv(out_path)
    print(f"\n逐日報酬序列已存 {out_path.relative_to(Path(__file__).parent)}"
          f"（gitignored，供下一輪接續分析用）")


if __name__ == "__main__":
    main()
