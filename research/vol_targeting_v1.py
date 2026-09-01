"""#15 波動度目標化部位配置 Vol-Targeting —— 第1關sanity第一版
（2026-09-02，`HYPOTHESIS_QUEUE_PROTOCOL.md`排程首次試跑）。

**背景**：`HYPOTHESIS_QUEUE.md`#15——這個專案至今排隊測過的九條假設
（Weinstein/CTA/PEAD/Carry/殘差動量/regime輪動/低波/類股輪動/產業內相對
強度/BAB/三大法人連續買超/月營收事件效應）清一色是「選股」維度（挑哪些
標的），這條刻意測試完全正交的另一個維度：edge是否在「部位大小配置」
本身，不涉及任何選股邏輯——用滾動已實現波動度動態調整整體曝險，維持
目標年化波動率，跟`regime_overlay.py`（#10，離散regime分組×固定曝險表）
是機制上不同的做法：這裡是**連續**函數（曝險反比於當下量到的波動度），
不是離散分組，經濟理由也不同（風險平價/波動度目標化文獻：Moreira & Muir
2017「Volatility-Managed Portfolios」——固定波動度水準下，risk-adjusted
報酬可能優於固定曝險，因為報酬對波動度的敏感度不是線性的）。

**測試對象（跟`regime_overlay.py`sanity同一個理由）**：TAIEX買進持有本身，
因為不依賴任何選股候選——這條假設可以獨立於Carry/其他候選判定結果先跑，
不用等其他選股類假設先過關（`HYPOTHESIS_QUEUE.md`#15原文）。

**曝險規則（第一版，非搜尋/優化，方向正確的先驗）**：
  - `realized_vol[d]`：60交易日滾動已實現波動度（年化，`rolling(60).std()×
    sqrt(252)`），用當下及之前的日報酬，PIT-safe。
  - `TARGET_VOL=0.15`（15%年化）：TAIEX歷史已實現波動度典型落在18~25%
    區間（這輪會印出實際數字驗證這個假設），15%是一個低於典型水準、會
    讓機制在多數時候產生有意義降曝險效果的目標值，不是刻意挑到剛好讓
    結果好看的數字——事前選定，不事後調整。
  - `exposure[d] = clip(TARGET_VOL / realized_vol[d], 0.0, 1.0)`：**這個
    專案的版本刻意不允許槓桿**（上限鎖在1.0，不是文獻常見的可以超過1.0），
    理由跟`CLAUDE.md`「資本保全優先」原則一致——用保證金放大曝險本身就是
    額外風險/成本來源，不在這輪的驗證範圍內；意味著這個版本只能在高波動
    期降曝險、不能在低波動期加碼超過100%，跟regime_overlay一樣是「單邊
    防禦型」的曝險調整，不是雙邊機制。這個差異明確記錄，不是疏漏。

**曝險/報酬的時序對齊（避免未來函數，完全比照`regime_overlay.py`的作法）**：
`overlay_return[d] = raw_return[d] * exposure[d-1]`（`exposure.shift(1)`）——
`exposure[d]`是「收盤後才知道」的狀態，最早只能影響下一個交易日的部位。

**這輪只做第1關sanity，不是完整策略驗證**：驗證機制本身有沒有做對事，
不是PASS/FAIL判定：①曝險分布非常數/非退化；②機制方向正確（realized_vol
越高、exposure越低，相關係數應顯著為負）；③已知危機期間（2018Q4貿易戰/
2020Q1新冠/2022全年空頭）overlay的平均曝險應明顯低於1.0、MDD應改善；
④TRAIN/VAL兩期的實際已實現波動度（overlay後）應比baseline更接近
TARGET_VOL（機制真的在「目標化」波動度，不是空轉）。真正的第2關（隨機
控制組）留給下一輪——「連續sizing規則」的隨機對照組本身需要另外設計
（隨機打亂曝險序列的時間順序？隨機決定sizing窗口？），不是這輪的範圍。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from factor_ic import START_DATE
from finmind_client import load_dev
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

TARGET_VOL = 0.15          # 年化目標波動率，15%，事前綁定不事後調整
VOL_WINDOW = 60             # 滾動已實現波動度視窗（交易日）
MAX_EXPOSURE = 1.00         # 不允許槓桿，見檔案docstring說明理由
MIN_EXPOSURE = 0.00

# 沿用regime_overlay.py同一組已知危機期間，供sanity交叉核對兩種機制在同樣
# 期間內的行為是否一致（都應該降曝險），不是這輪新發明的清單。
KNOWN_CRISIS_WINDOWS = {
    "2018Q4貿易戰急跌": ("2018-10-01", "2018-12-31"),
    "2020Q1新冠崩盤": ("2020-02-01", "2020-04-30"),
    "2022全年空頭": ("2022-01-01", "2022-12-31"),
}


def compute_vol_targeting(market_df: pd.DataFrame) -> pd.DataFrame:
    """輸入含`date`/`close`欄位的市場資料，回傳新增`raw_return`/`realized_vol`/
    `exposure`/`exposure_lagged`/`overlay_return`/`baseline_equity`/
    `overlay_equity`欄位的副本。PIT-safe：`realized_vol`只用`rolling()`，
    `exposure`套用時用`shift(1)`避免未來函數。"""
    d = market_df.sort_values("date").reset_index(drop=True).copy()
    d["raw_return"] = d["close"].pct_change()
    d["realized_vol"] = d["raw_return"].rolling(VOL_WINDOW, min_periods=VOL_WINDOW).std() * np.sqrt(252)
    with np.errstate(divide="ignore", invalid="ignore"):
        raw_exposure = TARGET_VOL / d["realized_vol"]
    d["exposure"] = raw_exposure.clip(lower=MIN_EXPOSURE, upper=MAX_EXPOSURE)
    d.loc[d["realized_vol"].isna(), "exposure"] = np.nan
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
                "sortino": float("nan"), "mdd_pct": float("nan"), "calmar": float("nan"), "n_days": n_days}
    total_return = float(equity.iloc[-1] / equity.iloc[0])
    years = n_days / 252.0
    cagr = total_return ** (1 / years) - 1
    ann_vol = float(ret.std() * np.sqrt(252))
    sharpe = float(ret.mean() / ret.std() * np.sqrt(252)) if ret.std() > 0 else float("nan")
    downside = ret[ret < 0]
    downside_std = float(downside.std() * np.sqrt(252)) if len(downside) > 1 else float("nan")
    sortino = float(ret.mean() * 252 / downside_std) if downside_std and downside_std > 0 else float("nan")
    running_max = equity.cummax()
    drawdown = equity / running_max - 1
    mdd = float(drawdown.min())
    calmar = (cagr / abs(mdd)) if mdd != 0 else float("nan")
    return {"cagr_pct": cagr * 100, "ann_vol_pct": ann_vol * 100, "sharpe": sharpe,
            "sortino": sortino, "mdd_pct": mdd * 100, "calmar": calmar, "n_days": n_days}


def compare_baseline_vs_overlay(d: pd.DataFrame, label: str) -> dict:
    base = _metrics(d["baseline_equity"], d["raw_return"])
    over = _metrics(d["overlay_equity"], d["overlay_return"])
    print(f"\n=== {label} ({d['date'].iloc[0]} ~ {d['date'].iloc[-1]}, n={len(d)}) ===")
    print(f"  baseline(買進持有): CAGR={base['cagr_pct']:+.2f}%  年化波動={base['ann_vol_pct']:.2f}%  "
          f"Sharpe={base['sharpe']:.2f}  Sortino={base['sortino']:.2f}  MDD={base['mdd_pct']:.2f}%  "
          f"Calmar={base['calmar']:.2f}")
    print(f"  vol-target(overlay): CAGR={over['cagr_pct']:+.2f}%  年化波動={over['ann_vol_pct']:.2f}%  "
          f"Sharpe={over['sharpe']:.2f}  Sortino={over['sortino']:.2f}  MDD={over['mdd_pct']:.2f}%  "
          f"Calmar={over['calmar']:.2f}")
    mdd_improved = over["mdd_pct"] > base["mdd_pct"]
    closer_to_target = abs(over["ann_vol_pct"] / 100 - TARGET_VOL) < abs(base["ann_vol_pct"] / 100 - TARGET_VOL)
    print(f"  MDD是否改善: {'是' if mdd_improved else '否'}（{base['mdd_pct']:.2f}% -> {over['mdd_pct']:.2f}%）")
    print(f"  已實現波動是否比baseline更接近目標{TARGET_VOL*100:.0f}%: "
          f"{'是' if closer_to_target else '否'}")
    return {"label": label, "baseline": base, "overlay": over,
            "mdd_improved": mdd_improved, "closer_to_target": closer_to_target}


def crisis_window_check(d: pd.DataFrame) -> None:
    print("\n--- 已知危機期間 曝險/MDD 檢查（sanity，不是回測期間切分）---")
    for name, (start, end) in KNOWN_CRISIS_WINDOWS.items():
        window = d[(d["date"] >= start) & (d["date"] <= end)]
        if window.empty:
            print(f"  {name}: 該期間資料為0筆（可能被holdout邊界排除或資料尚未涵蓋），跳過")
            continue
        avg_exposure = float(window["exposure_lagged"].mean())
        window_base = _metrics(window["baseline_equity"] / window["baseline_equity"].iloc[0],
                                window["raw_return"])
        window_over = _metrics(window["overlay_equity"] / window["overlay_equity"].iloc[0],
                                window["overlay_return"])
        print(f"  {name} ({start}~{end}, n={len(window)}): 平均滯後曝險={avg_exposure:.2f}  "
              f"窗內baseline MDD={window_base['mdd_pct']:.2f}%  窗內overlay MDD={window_over['mdd_pct']:.2f}%")


def random_control(d: pd.DataFrame, n_draws: int = 100, seed: int = 20260902) -> dict:
    """第2關隨機控制組（輕量版，本輪加做，非硬性要求但計算便宜就一併做掉）：
    打亂`exposure_lagged`的時間順序（保留邊際分布——一樣有60%左右天數在上限
    1.0、一樣的min/max/mean，只是跟哪一天配對是隨機的），重新套用到同一組
    `raw_return`序列上，算出Sharpe/CAGR/MDD的null分布。這在測「vol-targeting
    的『擇時』本身有沒有加值」，不是測「降曝險這個動作本身有沒有加值」——
    後者gate1已經看到MDD改善，但如果隨機時點降曝險一樣能達到差不多的Sharpe/
    MDD，代表edge不在「用realized_vol挑時機」這個機制上，只是單純「平均曝險
    比100%低」的效果，本質上是`HYPOTHESIS_QUEUE.md`快殺標準列的偽影家族之一
    （改變曝險力道）。"""
    rng = np.random.default_rng(seed)
    exposure_vals = d["exposure_lagged"].to_numpy()
    raw_ret = d["raw_return"].to_numpy()
    real_sharpe = float(d["overlay_return"].mean() / d["overlay_return"].std() * np.sqrt(252))
    real_equity = (1 + d["overlay_return"]).cumprod()
    real_mdd = float((real_equity / real_equity.cummax() - 1).min())
    real_cagr = float(real_equity.iloc[-1] ** (252 / len(real_equity)) - 1)

    shuffled_sharpes, shuffled_cagrs, shuffled_mdds = [], [], []
    for _ in range(n_draws):
        perm = rng.permutation(exposure_vals)
        sim_ret = raw_ret * perm
        sim_ret_s = pd.Series(sim_ret)
        if sim_ret_s.std() == 0 or sim_ret_s.isna().all():
            continue
        shuffled_sharpes.append(float(sim_ret_s.mean() / sim_ret_s.std() * np.sqrt(252)))
        sim_equity = (1 + sim_ret_s).cumprod()
        shuffled_mdds.append(float((sim_equity / sim_equity.cummax() - 1).min()))
        shuffled_cagrs.append(float(sim_equity.iloc[-1] ** (252 / len(sim_equity)) - 1))

    sharpe_pctl = 100.0 * float(np.mean(np.array(shuffled_sharpes) <= real_sharpe))
    cagr_pctl = 100.0 * float(np.mean(np.array(shuffled_cagrs) <= real_cagr))
    mdd_pctl = 100.0 * float(np.mean(np.array(shuffled_mdds) <= real_mdd))  # MDD越不負(越大)代表越好

    print(f"\n--- 第2關（輕量版）隨機控制組：打亂exposure時序，N={len(shuffled_sharpes)}draws ---")
    print(f"  真實Sharpe={real_sharpe:.3f}  打亂分布mean={np.mean(shuffled_sharpes):.3f} "
          f"median={np.median(shuffled_sharpes):.3f}  真實值percentile={sharpe_pctl:.1f}")
    print(f"  真實CAGR={real_cagr*100:+.2f}%  打亂分布mean={np.mean(shuffled_cagrs)*100:+.2f}% "
          f"真實值percentile={cagr_pctl:.1f}")
    print(f"  真實MDD={real_mdd*100:.2f}%  打亂分布mean={np.mean(shuffled_mdds)*100:.2f}% "
          f"真實值percentile={mdd_pctl:.1f}（越高代表真實MDD比打亂分布多數情況更淺）")
    return {"real_sharpe": real_sharpe, "sharpe_percentile": sharpe_pctl,
            "real_cagr": real_cagr, "cagr_percentile": cagr_pctl,
            "real_mdd": real_mdd, "mdd_percentile": mdd_pctl}


def main():
    print(f"載入TAIEX市場資料...（TARGET_VOL={TARGET_VOL*100:.0f}%, "
          f"VOL_WINDOW={VOL_WINDOW}日, MAX_EXPOSURE={MAX_EXPOSURE:.2f}）")
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in vol_targeting_v1")
    market_df = prepare_market_data(market_raw)

    dev_df = holdout.cap_to_dev(market_df)
    print(f"  TRAIN+VAL範圍: {dev_df['date'].min()} ~ {dev_df['date'].max()}, n={len(dev_df)}天")

    full = compute_vol_targeting(dev_df)
    train = full[full["date"] <= holdout.TRAIN_END].reset_index(drop=True)
    val = full[full["date"] > holdout.TRAIN_END].reset_index(drop=True)

    print("\n--- Sanity①：exposure分布是否非常數/非退化 ---")
    exp_valid = full["exposure"].dropna()
    print(f"  min={exp_valid.min():.3f}  max={exp_valid.max():.3f}  mean={exp_valid.mean():.3f}  "
          f"std={exp_valid.std():.3f}  被上限1.0截斷天數占比={100.0*(exp_valid>=0.999).mean():.1f}%")

    print("\n--- Sanity②：機制方向是否正確（realized_vol越高exposure應越低）---")
    corr = full[["realized_vol", "exposure"]].dropna().corr().iloc[0, 1]
    print(f"  realized_vol vs exposure 相關係數={corr:.3f}"
          f"（{'方向正確(顯著負相關)' if corr < -0.3 else '方向不符預期或太弱，需檢查'}）")

    print("\n--- Sanity③：TAIEX歷史已實現波動度水準（驗證TARGET_VOL選得合不合理）---")
    print(f"  全期間realized_vol：mean={full['realized_vol'].mean()*100:.2f}%  "
          f"median={full['realized_vol'].median()*100:.2f}%  "
          f"(TARGET_VOL={TARGET_VOL*100:.0f}% 是否低於典型水準："
          f"{'是' if TARGET_VOL < full['realized_vol'].median() else '否，需重新檢視'})")

    print("\n--- Sanity④：TRAIN/VAL/全期間 baseline vs vol-targeting overlay ---")
    train_result = compare_baseline_vs_overlay(train, "TRAIN")
    val_result = compare_baseline_vs_overlay(val, "VALIDATION")
    full_result = compare_baseline_vs_overlay(full, "TRAIN+VAL全期間")

    crisis_window_check(full)

    control_result = random_control(full)

    print("\n--- 結論（這輪的性質：工具能力就緒+第1關sanity，非PASS/FAIL判定）---")
    checks = {
        "exposure非常數": exp_valid.std() > 0.01,
        "機制方向正確(負相關<-0.3)": corr < -0.3,
        "TRAIN期波動更接近目標": train_result["closer_to_target"],
        "VAL期波動更接近目標": val_result["closer_to_target"],
        "全期間MDD改善": full_result["mdd_improved"],
    }
    for name, ok in checks.items():
        print(f"  {name}: {'PASS' if ok else 'FAIL'}")
    all_pass = all(checks.values())
    print(f"\n  第1關sanity綜合結果: {'全部通過，可進第2關（隨機控制組）' if all_pass else '有項目未過，需檢視上方細節再決定是否繼續'}")


if __name__ == "__main__":
    main()
