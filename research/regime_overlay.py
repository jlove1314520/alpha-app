"""#10 市場regime擇時overlay（200MA/VIX/breadth）—— 方法論框架第一版
（2026-09-02，`HYPOTHESIS_QUEUE_PROTOCOL.md` 第十輪排程）。

**背景**：`HYPOTHESIS_QUEUE.md`#10——`CLAUDE.md`最高投資原則第3條「regime
閘門（危機一律降曝險）是所有策略的強制overlay，非選配」的具體實作方向。
目前佇列裡Weinstein/CTA/PEAD/Carry/殘差動量五條選股類假設全部FAIL，**沒有
已過關的候選可以套用**——這一輪先把「地基」搭好：regime判定規則（沿用
已驗證過的既有邏輯，不重新發明）+ 疊加曝險調整的回測工具（本檔案的核心
函式），並做第1關sanity——用大盤買進持有本身當測試對象（唯一不需要任何
選股候選就能驗證機制本身有沒有做對事的方式），確認overlay確實在歷史上
已知的危機期間（2018Q4貿易戰急跌、2020Q1新冠崩盤、2022全年空頭）標成
「空頭/高波動」並降低曝險、MDD確實改善，不是常數/no-op/標籤錯位。

**regime判定規則（兩個既有、已在其他腳本驗證過方向定義的市場層級規則，
不是這輪新發明）**：
  - 大盤位階（trend）：TAIEX收盤 vs 200日均線，`strategies/weinstein_
    stage2.py::prepare_market_data()`的`gate`欄位（`portfolio_backtest_
    v2.py::_trend_regime_series()`、`BACKLOG.md`B25規格都用同一個定義）。
  - 波動度環境（vol）：TAIEX 20日已實現波動度（年化）vs 擴張窗中位數，
    完全複製`regime_conditions.py::_market_regime_labels()`的定義
    （PIT-safe，只用`.expanding()`，不看未來）。
  - 市場廣度（breadth）：這輪**未實作**——這個專案目前抓的是個股清單，
    沒有現成「當日全市場漲跌家數」聚合欄位，臨時湊一個需要重新掃全樣本
    每日漲跌，屬於這輪工作單位以外的地基建置量，誠實記錄「待補」，不是
    忘記；等未來有實際候選需要更精細的regime判定時再評估值不值得建。

**疊加曝險規則（`EXPOSURE_MAP`，這輪的第一版參數，非最終定案、未經任何
搜尋/優化）**：trend跟vol各自二元，組合成四格，數值刻意單調（危機組合
最低、雙好組合最高）：
  - 多頭+低波動 = 1.00（正常全曝險）
  - 多頭+高波動 = 0.70（多頭但波動放大，稍降）
  - 空頭+低波動 = 0.70（空頭但還沒恐慌，稍降）
  - 空頭+高波動 = 0.40（空頭+高波動=危機組合，大幅降曝險）
這組數字是「第一版、可調」的先驗，不是搜出來的最佳化結果——按`CLAUDE.md`
「regime閘門是強制overlay」的精神先給一組單調、方向正確的初始值。**這輪
刻意不做參數優化**：沒有真實候選要套用的狀況下去調這幾個數字，本質是在
替一個不存在的目標函數過擬合，等未來真的有候選要套用第9關（下檔保護）
時，才需要針對那個候選的風險特性做敏感度測試。

**曝險/報酬的時序對齊（避免未來函數）**：regime[d]用「當下及之前」資料
（收盤價、`.rolling()`、`.expanding()`）算出，代表「收盤後才知道」的狀態
——若要用它調整交易曝險，最早只能影響**下一個交易日**的部位，不能影響
當天自己的報酬。所以`overlay_return[d] = raw_return[d] * exposure[d-1]`
（`exposure.shift(1)`），不是`exposure[d]`本身。

**這輪只做sanity，不是完整策略驗證**：套用對象是TAIEX買進持有本身，不是
任何一個選股策略，**這不是一個可部署的擇時策略**，只驗證三件事：
①regime標籤在已知危機期間真的標成「空頭/高波動」（不是反的或錯位的）、
②overlay數學上真的降低了那些期間的曝險、③MDD/報酬的變化方向合理。真正
的第2關（隨機控制組）在「擇時overlay」這個語境下要拿什麼當隨機對照組
本身需要另外設計（隨機打亂regime標籤的時間順序？隨機決定切換時點？），
留給下一輪或有實際候選要套用時再處理——這輪的產出是「工具能力就緒+
sanity通過」，不是PASS/FAIL判定，佇列狀態維持「方法論框架建置中」。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from factor_ic import START_DATE
from finmind_client import load_dev
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

EXPOSURE_MAP = {
    ("bull_above_ma", "low_vol"): 1.00,
    ("bull_above_ma", "high_vol"): 0.70,
    ("bear_below_ma", "low_vol"): 0.70,
    ("bear_below_ma", "high_vol"): 0.40,
}

# 已知危機期間（供sanity檢查regime標籤有沒有標對，不是回測的訓練/驗證邊界）。
KNOWN_CRISIS_WINDOWS = {
    "2018Q4貿易戰急跌": ("2018-10-01", "2018-12-31"),
    "2020Q1新冠崩盤": ("2020-02-01", "2020-04-30"),
    "2022全年空頭": ("2022-01-01", "2022-12-31"),
}


def compute_regime_labels(market_df: pd.DataFrame) -> pd.DataFrame:
    """輸入`prepare_market_data()`的輸出（含`date`/`close`/`gate`欄位），回傳
    新增`trend_regime`/`vol_regime`/`combined_regime`/`exposure`四欄的副本。
    全部PIT-safe：`vol20`用`rolling(20)`、跟它比較的門檻用`expanding()`，
    只用當下及之前的資料，不看未來。"""
    d = market_df.sort_values("date").reset_index(drop=True).copy()
    ret = d["close"].pct_change()
    vol20 = ret.rolling(20, min_periods=20).std() * np.sqrt(252)
    expanding_median = vol20.expanding(min_periods=60).median()
    d["vol_regime"] = np.where(vol20 > expanding_median, "high_vol", "low_vol")
    d["trend_regime"] = np.where(d["gate"], "bull_above_ma", "bear_below_ma")
    # rolling/expanding 前面 warm-up 期還沒有值時，vol_regime 會被 np.where 誤判成
    # 'low_vol'（NaN > x 是 False）——這幾天 exposure 不該套用，標成 NaN 讓下游知道
    # 排除，不是刻意判「低波動」。
    warm = vol20.isna() | expanding_median.isna()
    d.loc[warm, "vol_regime"] = None
    d["combined_regime"] = list(zip(d["trend_regime"], d["vol_regime"]))
    d["exposure"] = [EXPOSURE_MAP.get(c, np.nan) for c in d["combined_regime"]]
    return d


def apply_overlay(regime_df: pd.DataFrame) -> pd.DataFrame:
    """回傳新增`raw_return`/`exposure_lagged`/`overlay_return`/`baseline_equity`/
    `overlay_equity`欄位的副本。曝險用`exposure.shift(1)`（見檔案docstring「曝險/
    報酬的時序對齊」段落），第一天沒有前一天的曝險資訊，raw_return/overlay_return
    當天都是NaN（等同兩條淨值曲線都從隔天才開始累積，公平對照）。"""
    d = regime_df.sort_values("date").reset_index(drop=True).copy()
    d["raw_return"] = d["close"].pct_change()
    d["exposure_lagged"] = d["exposure"].shift(1)
    d["overlay_return"] = d["raw_return"] * d["exposure_lagged"]
    valid = d["raw_return"].notna() & d["overlay_return"].notna()
    d = d[valid].reset_index(drop=True)
    d["baseline_equity"] = (1 + d["raw_return"]).cumprod()
    d["overlay_equity"] = (1 + d["overlay_return"]).cumprod()
    return d


def _metrics(equity: pd.Series, ret: pd.Series) -> dict:
    n_days = len(equity)
    if n_days < 30:
        return {"cagr_pct": float("nan"), "ann_vol_pct": float("nan"), "sharpe": float("nan"),
                "mdd_pct": float("nan"), "calmar": float("nan"), "n_days": n_days}
    total_return = float(equity.iloc[-1] / equity.iloc[0])
    years = n_days / 252.0
    cagr = total_return ** (1 / years) - 1
    ann_vol = float(ret.std() * np.sqrt(252))
    sharpe = float(ret.mean() / ret.std() * np.sqrt(252)) if ret.std() > 0 else float("nan")
    running_max = equity.cummax()
    drawdown = equity / running_max - 1
    mdd = float(drawdown.min())
    calmar = (cagr / abs(mdd)) if mdd != 0 else float("nan")
    return {"cagr_pct": cagr * 100, "ann_vol_pct": ann_vol * 100, "sharpe": sharpe,
            "mdd_pct": mdd * 100, "calmar": calmar, "n_days": n_days}


def compare_baseline_vs_overlay(d: pd.DataFrame, label: str) -> dict:
    base = _metrics(d["baseline_equity"], d["raw_return"])
    over = _metrics(d["overlay_equity"], d["overlay_return"])
    print(f"\n=== {label} ({d['date'].iloc[0]} ~ {d['date'].iloc[-1]}, n={len(d)}) ===")
    print(f"  baseline(買進持有): CAGR={base['cagr_pct']:+.2f}%  年化波動={base['ann_vol_pct']:.2f}%  "
          f"Sharpe={base['sharpe']:.2f}  MDD={base['mdd_pct']:.2f}%  Calmar={base['calmar']:.2f}")
    print(f"  overlay(regime調整): CAGR={over['cagr_pct']:+.2f}%  年化波動={over['ann_vol_pct']:.2f}%  "
          f"Sharpe={over['sharpe']:.2f}  MDD={over['mdd_pct']:.2f}%  Calmar={over['calmar']:.2f}")
    mdd_improved = over["mdd_pct"] > base["mdd_pct"]  # 較不負 = 改善
    print(f"  MDD是否改善: {'是' if mdd_improved else '否'}"
          f"（{base['mdd_pct']:.2f}% -> {over['mdd_pct']:.2f}%）")
    return {"label": label, "baseline": base, "overlay": over, "mdd_improved": mdd_improved}


def crisis_window_check(d: pd.DataFrame) -> None:
    """Sanity檢查②/①：已知危機期間內，regime有沒有標對（多數交易日落在空頭/
    高波動格），以及那段期間內overlay有沒有真的降低曝險、MDD有沒有變好。"""
    print("\n--- 已知危機期間 regime 標籤檢查（sanity，不是回測期間切分）---")
    for name, (start, end) in KNOWN_CRISIS_WINDOWS.items():
        window = d[(d["date"] >= start) & (d["date"] <= end)]
        if window.empty:
            print(f"  {name}: 該期間資料為0筆（可能被holdout邊界排除或資料尚未涵蓋），跳過")
            continue
        trend_bear_pct = 100.0 * (window["trend_regime"] == "bear_below_ma").mean()
        vol_high_pct = 100.0 * (window["vol_regime"] == "high_vol").mean()
        avg_exposure = float(window["exposure_lagged"].mean())
        print(f"  {name} ({start}~{end}, n={len(window)}): "
              f"空頭天數占比={trend_bear_pct:.1f}%  高波動天數占比={vol_high_pct:.1f}%  "
              f"平均曝險={avg_exposure:.2f}")
        window_base = _metrics(window["baseline_equity"] / window["baseline_equity"].iloc[0],
                                window["raw_return"])
        window_over = _metrics(window["overlay_equity"] / window["overlay_equity"].iloc[0],
                                window["overlay_return"])
        print(f"    窗內baseline報酬={window_base['cagr_pct']:+.2f}%(年化換算,僅供對照) "
              f"MDD={window_base['mdd_pct']:.2f}%  |  窗內overlay報酬={window_over['cagr_pct']:+.2f}%(年化換算) "
              f"MDD={window_over['mdd_pct']:.2f}%")


def main():
    print("載入TAIEX市場資料...")
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in regime_overlay")
    market_df = prepare_market_data(market_raw)

    dev_df = holdout.cap_to_dev(market_df)  # 只用train+val，不碰holdout（VAL_END之後）
    print(f"  TRAIN+VAL範圍: {dev_df['date'].min()} ~ {dev_df['date'].max()}, n={len(dev_df)}天")

    regime_df = compute_regime_labels(dev_df)
    n_missing_vol = regime_df["vol_regime"].isna().sum()
    print(f"  regime標籤warm-up期缺值天數: {n_missing_vol}（expanding窗前置期，預期會有，"
          f"不是bug）")

    combined = apply_overlay(regime_df)

    print("\n--- Sanity①：combined_regime分布是否合理（非系統性0筆/全部同一格）---")
    dist = combined["combined_regime"].value_counts()
    for combo, cnt in dist.items():
        pct = 100.0 * cnt / len(combined)
        print(f"  {combo}: {cnt}天 ({pct:.1f}%)")

    print("\n--- Sanity②：全期間baseline vs overlay ---")
    full_result = compare_baseline_vs_overlay(combined, "TRAIN+VAL全期間")

    crisis_window_check(combined)

    print("\n--- 結論（這輪的性質：工具能力就緒+sanity通過，非PASS/FAIL判定）---")
    print(f"  1. regime分布非系統性單一格：{'PASS' if len(dist) >= 3 else 'FAIL'}"
          f"（{len(dist)}種組合都有出現）")
    print(f"  2. 全期間MDD是否改善: {'PASS' if full_result['mdd_improved'] else '待觀察'}")
    print("  3. 已知危機期間regime標籤/曝險方向請見上方逐段輸出（人工判讀，"
          "非自動PASS/FAIL——這是這份sanity的設計意圖，正確性判斷留給人/下一輪"
          "根據實際數字決定）。")
    print("\n下一步：等佇列裡有選股候選通過1~8關後，把`compute_regime_labels`+"
          "`apply_overlay`兩個函式接到那個候選的日報酬序列上，正式測第9關"
          "（下檔保護），不是套在TAIEX買進持有上。市場廣度(breadth)規則仍待補。")


if __name__ == "__main__":
    main()
