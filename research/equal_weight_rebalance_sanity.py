"""`HYPOTHESIS_QUEUE.md` #29 等權重再平衡溢酬 Diversification Return /
Equal-Weight Rebalancing Premium 第1關 sanity。

**這輪只做sanity，不做判定**：依`HYPOTHESIS_QUEUE_PROTOCOL.md`「這一輪先把
地基做好」原則——確認等權重再平衡後的組合報酬序列非退化（無NaN爆炸）、
再平衡確實有觸發（拉回前權重真的有漂移，不是no-op）、方向不是明顯反過來
（不強求本輪判定PASS/FAIL，留給第2關以後）。

**基準操作化的誠實揭露（跟`HYPOTHESIS_QUEUE.md`#29條目文字有一處刻意偏離，
必須在這裡講清楚）**：#29條目原文寫的比較對象是「同一組標的市值加權
（buy-and-hold，不再平衡）」，但這個專案目前**沒有任何市值/流通股數資料源**
（`factors.py`/`universe.py`/`adjust.py`都查證過，沒有`market_cap`欄位，
`TaiwanStockPER`的PBR只給股價淨值比不給流通股數，換算市值需要新的資料工程）
——而#29條目「資料可行性」段落原本承諾「不需要任何新的API呼叫或新資料工程」，
兩者互相矛盾，這裡選擇遵守後者（不新增資料工程），基準改用**「同一組標的、
t0等權重起跑、之後永不主動調整（純buy-and-hold）」**，而不是市值加權。這其實
是Booth & Fama (1992) diversification return文獻更常見、更乾淨的操作化方式
——因為比較對象跟處理組共用完全相同的起始權重跟股票池，唯一差異就是「有沒有
定期把權重拉回等權重」這個機械動作本身，不會混進「等權 vs 市值加權」這個
額外的規模傾斜差異（跟`f_low_vol`/`f_bab`已死的教訓一致——那兩條就是被
「排序本身」以外的beta/規模曝險污染了結論），反而更精確隔離出這條假設真正
要測的機制。

**方法**：沿用`factor_ic.py`既有300檔快取樣本（`SAMPLE_SEED`/`SAMPLE_SIZE`，
跟#11/#17/#28共用同一個宇宙），用`adjust.py::adjusted_price_series`
（已holdout-safe capped在VAL_END）取每檔`adj_close`。為了sanity階段先求
簡單乾淨，只保留在整個測試視窗（`SNAPSHOT_START`..`VAL_END`）頭尾都有值、
中間缺口不超過5個交易日（可forward/backward-fill）的股票組成靜態panel——
**這是sanity階段刻意的簡化，隱含存活者偏差，不是portfolio層最終判定會用的
處理方式**，下一輪若要往下走需要視情況改成動態成分池或明確揭露此限制不解決。
模擬兩條路徑：①`buyhold`——t0等權重，之後任由權重隨個股報酬漂移，永不調整；
②`rebalanced`——每`REBAL_FREQ`（21交易日，跟`dividend_yield_portfolio_v1`/
`f52w_high_portfolio_v1`同一個月頻換股慣例）交易日拉回等權重一次。

2026-09-04 由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程新增，佇列#29第1關
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

REBAL_FREQ = 21  # trading days, ~monthly
MIN_HISTORY_DAYS = 500  # 跟pair_trading_sanity.py同一個門檻（總歷史長度，非視窗內涵蓋度）
WINDOW_START = SNAPSHOT_START  # 2015-01-01，跟factor_ic系列cheap gate同一個起點，方便跨假設比較
WINDOW_END = holdout.VAL_END


def load_prices(sample_ids: list[str]) -> dict[str, pd.Series]:
    """回傳 stock_id -> date-indexed adj_close Series，capped at VAL_END（沿用
    pair_trading_sanity.py同一個容錯與門檻慣例，這裡獨立複製一份而非import，
    保持每支假設腳本可獨立重跑的慣例）。"""
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
    """把個股adj_close對齊成同一組交易日的panel，只留下視窗頭尾5個交易日內
    都有值的股票（存活者偏差，docstring已誠實揭露），中間缺口<=5個交易日用
    ffill/bfill補，超過的整支丟棄不硬湊。"""
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
    df = df.dropna(axis=1)  # 仍有殘留缺口(超過5個交易日)的欄位整支丟棄
    return df


def simulate(panel: pd.DataFrame, rebal_freq: int) -> pd.DataFrame:
    """回傳index=交易日、欄位buyhold_ret/rebal_ret（當日報酬率，非累積）的
    DataFrame，attrs紀錄再平衡事件數與每次拉回前的權重離散度。"""
    rets = panel.pct_change().dropna(how="all")
    rets = rets.fillna(0.0)  # 防禦性補0——經build_panel清理後理論上不應再有NaN
    n = panel.shape[1]
    w_buyhold = np.full(n, 1.0 / n)
    w_rebal = np.full(n, 1.0 / n)
    buyhold_rets, rebal_rets, dispersions = [], [], []
    rebal_events = 0
    for t, (_, r) in enumerate(rets.iterrows()):
        r = r.values
        port_ret_bh = float(np.dot(w_buyhold, r))
        buyhold_rets.append(port_ret_bh)
        w_buyhold = w_buyhold * (1 + r)
        w_buyhold = w_buyhold / w_buyhold.sum()

        port_ret_rb = float(np.dot(w_rebal, r))
        rebal_rets.append(port_ret_rb)
        w_rebal = w_rebal * (1 + r)
        w_rebal = w_rebal / w_rebal.sum()
        if (t + 1) % rebal_freq == 0:
            dispersions.append(float(np.std(w_rebal)))
            w_rebal = np.full(n, 1.0 / n)
            rebal_events += 1

    out = pd.DataFrame({"buyhold_ret": buyhold_rets, "rebal_ret": rebal_rets}, index=rets.index)
    out.attrs["rebal_events"] = rebal_events
    out.attrs["pre_rebal_dispersion_mean"] = float(np.mean(dispersions)) if dispersions else float("nan")
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
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    print(f"樣本：{len(sample_ids)}檔(SEED={SAMPLE_SEED})，跟#11/#17/#28共用同一個300檔宇宙")
    prices = load_prices(sample_ids)
    print(f"  {len(prices)}/{len(sample_ids)}檔通過最低歷史長度門檻({MIN_HISTORY_DAYS}交易日)")

    panel = build_panel(prices)
    print(f"最終panel：{panel.shape[1]}檔股票 x {panel.shape[0]}個交易日"
          f"（{panel.index[0].date()}..{panel.index[-1].date()}），"
          f"視窗頭尾涵蓋度篩選(存活者偏差，見docstring)")

    if panel.shape[1] < 30:
        print(f"SANITY FAIL: 可用股票數({panel.shape[1]})過少，判結構性不可靠，不繼續")
        return

    sim = simulate(panel, REBAL_FREQ)
    expected_events = panel.shape[0] // REBAL_FREQ
    print(f"\n再平衡事件數：{sim.attrs['rebal_events']}次（{REBAL_FREQ}交易日一次，"
          f"理論上約{expected_events}次，{'一致' if sim.attrs['rebal_events'] == expected_events else '不一致，需檢查'}）")
    print(f"每次拉回前的權重離散度(std)平均：{sim.attrs['pre_rebal_dispersion_mean']:.5f}"
          f"（>0代表權重真的有漂移、拉回動作不是no-op；若接近0代表個股報酬幾乎"
          f"完全同步，拉回不會改變任何東西，需要另外檢查資料是否有問題）")

    nan_check = int(sim.isna().sum().sum())
    inf_check = int(np.isinf(sim.values).sum())
    print(f"\n報酬序列NaN檢查：{nan_check}（應為0）  Inf檢查：{inf_check}（應為0）")

    periods = [
        (f"TRAIN({WINDOW_START}..{holdout.TRAIN_END})", sim.index <= pd.Timestamp(holdout.TRAIN_END)),
        (f"VAL({holdout.TRAIN_END}..{holdout.VAL_END})", sim.index > pd.Timestamp(holdout.TRAIN_END)),
        (f"FULL({WINDOW_START}..{holdout.VAL_END})", pd.Series(True, index=sim.index)),
    ]
    for period_label, mask in periods:
        sub = sim[mask]
        bh = summarize(sub["buyhold_ret"])
        rb = summarize(sub["rebal_ret"])
        premium = rb["total_return"] - bh["total_return"]
        print(f"\n=== {period_label} ({len(sub)}個交易日) ===")
        print(f"  buyhold(等權起始,不再平衡):     total_return={bh['total_return']:+.2%}  "
              f"ann_vol={bh['ann_vol']:.2%}  sharpe={bh['sharpe']:+.3f}  mdd={bh['mdd']:.2%}")
        print(f"  rebalanced(每{REBAL_FREQ}日拉回等權重): total_return={rb['total_return']:+.2%}  "
              f"ann_vol={rb['ann_vol']:.2%}  sharpe={rb['sharpe']:+.3f}  mdd={rb['mdd']:.2%}")
        print(f"  再平衡溢酬(rebalanced - buyhold)：{premium:+.2%}"
              f"（此輪僅sanity方向檢查，不是最終判定——第2關以後才會用隨機控制組"
              f"跟alpha顯著性正式判定）")

    out_path = Path(__file__).parent / "data" / "equal_weight_rebalance_sanity_daily_returns.csv"
    sim.to_csv(out_path)
    print(f"\n逐日報酬序列已存 {out_path.relative_to(Path(__file__).parent)}"
          f"（gitignored，供下一輪接續分析用）")


if __name__ == "__main__":
    main()
