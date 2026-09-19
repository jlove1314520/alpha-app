"""regime.替代A 成本前置關卡（1a-0）：只用訊號序列本身估換手與成本拖累，
完全不看報酬／MDD／任何績效數字，所以不構成「看結果再調規格」。
輸出：連續型200MA距離曝險的年化Σ|Δ曝險|與對應成本拖累，對照二元版(#243)。
"""
from __future__ import annotations
import sys
import numpy as np
import pandas as pd
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from factor_ic import START_DATE
from finmind_client import load_dev
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout
from regime_overlay_trend_filter_gate import COST_PER_UNIT_EXPOSURE_CHANGE as C

FLOOR = 0.5
MIN_PERIODS = 252


def continuous_exposure(close: pd.Series, ma_window: int, k: float) -> pd.Series:
    ma = close.rolling(ma_window, min_periods=ma_window).mean()
    dist = close / ma - 1.0
    sd = dist.expanding(min_periods=MIN_PERIODS).std()
    risk_z = -dist / sd  # 越在均線下方越大；只用當下與過去資料(PIT-safe)
    return (1.0 - k * risk_z).clip(FLOOR, 1.0)


def main():
    raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(raw, context="regime_alt_a_cost_precheck")
    d = holdout.cap_to_train(prepare_market_data(raw)).sort_values("date").reset_index(drop=True)
    print(f"TRAIN {d['date'].min()} ~ {d['date'].max()} n={len(d)}  單位曝險變動成本={C*100:.3f}%")
    for ma in (140, 200, 260):
        for k in (0.35, 0.5, 0.65):
            e = continuous_exposure(d["close"], ma, k)
            v = e.dropna()
            yrs = len(v) / 245.0
            turn = v.diff().abs().sum() / yrs
            print(f"MA={ma} k={k}: 有效天數={len(v)} 年化Σ|Δ曝險|={turn:.2f} "
                  f"年化成本拖累={turn*C*100:.2f}% 平均曝險={v.mean():.3f} 半倉以下天數比={(v<=0.501).mean()*100:.1f}%")
    ma = d["close"].rolling(200, min_periods=200).mean()
    b = pd.Series(np.where(d["close"] > ma, 1.0, 0.5), index=d.index)[ma.notna()]
    yrs = len(b) / 245.0
    turn = b.diff().abs().sum() / yrs
    print(f"[對照]二元200MA: 年化Σ|Δ曝險|={turn:.2f} 年化成本拖累={turn*C*100:.2f}%")


if __name__ == "__main__":
    main()
