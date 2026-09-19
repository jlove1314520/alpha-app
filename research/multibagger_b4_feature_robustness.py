"""重構.B4：Q5撤回後的補救（PENDING_QUEUE.md「重構.B4」條目，2026-09-19
總司令原文指定）。

背景：重構.B3已把Q5原結論撤回——size_proxy（規模代理）分位門檻的
worst-case敏感度分析顯示，最佳百分位從原始的60%翻轉到worst-case下的
80%（見`multibagger_raw/five_questions_result_v2.json`
`star1_delisted_undercount.q5_sensitivity`），代表規模門檻本身不可判定。

這裡改問：在Q3/Q4已經量測過的其他起漲前特徵（`eps_yoy_pre`／`pe_pre`／
`ret_250d_pre`）裡，哪些特徵分組後的起飛率/下市率比值排名，對「32檔
仍未解決的delisted股票全部沒起飛且下市」這個worst-case假設最不敏感？
目標是找穩健的特徵，不是找樣本內最好看的切點。

方法（沿用★一/重構.B3已建好的機制，只換分組維度）：
1. 用`_build_stock_level_base()`同構的方式，對每個候選特徵取「該股票所有
   窗口的中位數」當股票層級代表值（跟size_proxy同一種聚合邏輯，語意一致：
   同一檔股票在不同時間點的特徵值會變動，中位數是對「這檔股票在觀察期內
   典型狀態」較穩健的代表）。
2. 用`_q5_from_stock_table()`（已泛化支援`size_col`參數）算原始的5個累計
   分位門檻（20/40/60/80/100）起飛率/下市率/比值表。
3. worst-case：32檔未解決delisted股票的這些特徵值我們一無所知（連
   size_proxy都測不到了，更不用說eps_yoy_pre這類需要更多期歷史財報的
   衍生特徵），所以用跟★一同一種「phantom sentinel」機制，但**測試兩個
   方向**（不是只測一個）：
     - LOW extreme（sentinel=該特徵已觀察最小值-1）：對應「財務體質差/
       動能差的公司更可能下市」這個經濟直覺（EPS年增衰退/報酬動能轉弱
       通常先於下市）——這是跟原始size_proxy設計同構的「困境徵兆在低端」
       假設，是本分析的主要（較嚴格）檢定方向。
     - HIGH extreme（sentinel=該特徵已觀察最大值+1）：次要的對照方向，
       誠實揭露其設計上的局限——本檔用的是「累計分位」（≤cutoff）結構
       而非互斥五分位，phantom放在高端只會被排除在20/40/60/80這幾個
       較小的累計組之外、只進入涵蓋全體的100%組，因此這個方向的檢定力
       天生較弱（幾乎不可能翻轉結論），不能被解讀成「兩個方向都測了所以
       一樣嚴格」，只是作為一個誠實的次要對照，不是本分析下結論的主要
       依據。
   [自行裁量] 為什麼不猜每個特徵各自的「真實」下市方向（例如pe_pre的
   下市方向不如eps_yoy_pre/ret_250d_pre直覺）：與其對每個特徵各自假設
   一個可能有偏誤的方向，統一測兩個方向、且明講何者是主要檢定/何者是
   次要對照，比較不會被「我剛好選了讓結論好看的方向」這種質疑打中。
4. 判準：「該特徵分組排名對worst-case穩健」＝原始最佳百分位與LOW extreme
   worst-case下的最佳百分位相同（HIGH extreme一致預期恆真，僅供參考不
   計入判準）。另外報一個更細的敏感度指標：5個分位點的排名（依比值排序）
   在原始vs LOW extreme worst-case下的Spearman等級相關，越接近1代表整體
   排名越穩定，不是只看最佳點有沒有變。

資料重用：跟`multibagger_five_questions_v2.py`（重構.B3）同一份磁碟快取
（`multibagger_raw/all_windows_stride6m_recovered.csv`、
`five_questions_result_v2.json`），不重打任何API。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from multibagger_five_questions_v2 import (
    RAW_DIR, _load_strata_info, _q5_from_stock_table,
)

FEATURES = ["size_proxy", "eps_yoy_pre", "pe_pre", "ret_250d_pre"]
# size_proxy 沿用 avg_trading_money_20d_pre（跟重構.B3的size_proxy定義完全一致），
# 其餘三個是原始欄位名。
FEATURE_SOURCE_COL = {
    "size_proxy": "avg_trading_money_20d_pre",
    "eps_yoy_pre": "eps_yoy_pre",
    "pe_pre": "pe_pre",
    "ret_250d_pre": "ret_250d_pre",
}


def _load_windows_df() -> pd.DataFrame:
    recovered_path = RAW_DIR / "all_windows_stride6m_recovered.csv"
    if recovered_path.exists():
        return pd.read_csv(recovered_path)
    return pd.read_csv(RAW_DIR / "all_windows_stride6m.csv")


def _load_unresolved_ids() -> list[str]:
    with open(RAW_DIR / "five_questions_result_v2.json", encoding="utf-8") as f:
        d = json.load(f)
    return d["star1_delisted_undercount"]["unresolved_stock_ids_used_in_worst_case"]


def _build_stock_level_feature_table(windows_df: pd.DataFrame, feature_name: str,
                                      strata_info: dict) -> pd.DataFrame:
    """每檔股票一列：status、該特徵的股票層級中位數、has_moonshot、
    population_weight、is_delisted。跟`_build_stock_level_base()`同構，
    只是把size_proxy換成任一候選特徵。"""
    source_col = FEATURE_SOURCE_COL[feature_name]
    pop_weight = {k: v["population_weight"] for k, v in strata_info.items()}
    g = windows_df.groupby("stock_id", as_index=False).agg(
        status=("status", "first"),
        _feat=(source_col, "median"),
        has_moonshot=("outcome", lambda s: bool((s == "moonshot").any())),
    )
    g = g.rename(columns={"_feat": feature_name})
    g["population_weight"] = g["status"].map(pop_weight).astype(float)
    g["is_delisted"] = (g["status"] == "delisted").astype(float)
    return g


def _best_pct(table: pd.DataFrame) -> dict | None:
    valid = table.dropna(subset=["起飛率_下市率_比值"])
    if valid.empty:
        return None
    row = valid.loc[valid["起飛率_下市率_比值"].idxmax()]
    return {"規模代理分位門檻_百分位": int(row["規模代理分位門檻_百分位"]),
            "比值": float(row["起飛率_下市率_比值"])}


def _rank_spearman(orig: pd.DataFrame, worst: pd.DataFrame) -> float | None:
    """兩個表都以「規模代理分位門檻_百分位」為key，比較「起飛率_下市率_比值」
    的排名相關性。只用兩表共同、非NaN的百分位點比較（通常5點都在）。"""
    o = orig.dropna(subset=["起飛率_下市率_比值"]).set_index("規模代理分位門檻_百分位")["起飛率_下市率_比值"]
    w = worst.dropna(subset=["起飛率_下市率_比值"]).set_index("規模代理分位門檻_百分位")["起飛率_下市率_比值"]
    common = o.index.intersection(w.index)
    if len(common) < 3:
        return None
    rho, _ = spearmanr(o.loc[common], w.loc[common])
    return float(rho) if not np.isnan(rho) else None


def _worst_case_one_direction(stock_df: pd.DataFrame, feature_name: str,
                               unresolved_ids: list[str], delisted_weight: float,
                               direction: str) -> pd.DataFrame:
    """direction: 'low' 用sentinel=min-1（主要/嚴格檢定），
    'high' 用sentinel=max+1（次要/寬鬆對照，見檔案docstring）。"""
    assert direction in ("low", "high")
    if direction == "low":
        sentinel = float(stock_df[feature_name].min(skipna=True)) - 1.0
    else:
        sentinel = float(stock_df[feature_name].max(skipna=True)) + 1.0
    phantom_rows = [{
        "stock_id": sid, "status": "delisted", feature_name: sentinel,
        "has_moonshot": False, "is_delisted": 1.0, "population_weight": delisted_weight,
    } for sid in unresolved_ids]
    worst_case = pd.concat([stock_df, pd.DataFrame(phantom_rows)], ignore_index=True)
    return _q5_from_stock_table(worst_case, size_col=feature_name)


def analyze_feature(windows_df: pd.DataFrame, strata_info: dict, feature_name: str,
                     unresolved_ids: list[str]) -> dict:
    stock_df = _build_stock_level_feature_table(windows_df, feature_name, strata_info)
    n_with_value = int(stock_df[feature_name].notna().sum())
    n_total = int(len(stock_df))

    original = _q5_from_stock_table(stock_df, size_col=feature_name)
    delisted_weight = strata_info["delisted"]["population_weight"]
    worst_low = _worst_case_one_direction(stock_df, feature_name, unresolved_ids, delisted_weight, "low")
    worst_high = _worst_case_one_direction(stock_df, feature_name, unresolved_ids, delisted_weight, "high")

    best_orig = _best_pct(original)
    best_low = _best_pct(worst_low)
    best_high = _best_pct(worst_high)

    survives_low = (best_orig is not None and best_low is not None
                    and best_orig["規模代理分位門檻_百分位"] == best_low["規模代理分位門檻_百分位"])
    survives_high = (best_orig is not None and best_high is not None
                      and best_orig["規模代理分位門檻_百分位"] == best_high["規模代理分位門檻_百分位"])

    return {
        "feature": feature_name,
        "n_stocks_with_value": n_with_value, "n_stocks_total": n_total,
        "coverage_pct": round(100 * n_with_value / n_total, 1) if n_total else None,
        "n_phantom_unresolved": len(unresolved_ids),
        "table_original": original.to_dict(orient="records"),
        "table_worst_case_low": worst_low.to_dict(orient="records"),
        "table_worst_case_high": worst_high.to_dict(orient="records"),
        "best_percentile_original": best_orig,
        "best_percentile_worst_case_low": best_low,
        "best_percentile_worst_case_high": best_high,
        "conclusion_survives_worst_case_low": survives_low,
        "conclusion_survives_worst_case_high_sanity_check": survives_high,
        "robust_by_main_criterion": survives_low,
        "rank_spearman_original_vs_worst_low": _rank_spearman(original, worst_low),
        "rank_spearman_original_vs_worst_high": _rank_spearman(original, worst_high),
    }


def main() -> None:
    windows_df = _load_windows_df()
    strata_info = _load_strata_info()
    unresolved_ids = _load_unresolved_ids()
    print(f"[B4] windows_df rows={len(windows_df)}, unresolved delisted phantoms={len(unresolved_ids)}")

    results = {}
    for feature_name in FEATURES:
        r = analyze_feature(windows_df, strata_info, feature_name, unresolved_ids)
        results[feature_name] = r
        print(f"[B4] {feature_name}: coverage={r['coverage_pct']}% "
              f"best_orig={r['best_percentile_original']} "
              f"best_worst_low={r['best_percentile_worst_case_low']} "
              f"survives_low={r['conclusion_survives_worst_case_low']} "
              f"rank_rho_low={r['rank_spearman_original_vs_worst_low']}")

    robust_features = [f for f, r in results.items() if r["robust_by_main_criterion"]]
    sensitive_features = [f for f, r in results.items() if not r["robust_by_main_criterion"]]
    print(f"[B4] 穩健（主判準存活）特徵: {robust_features}")
    print(f"[B4] 不穩健（主判準翻轉）特徵: {sensitive_features}")

    out = {
        "generated_from": "multibagger_b4_feature_robustness.py（重構.B4）",
        "method_note": (
            "累計分位（≤cutoff）結構下，LOW extreme sentinel是主要/嚴格檢定"
            "（phantom被推進最小的幾個累計組），HIGH extreme sentinel是次要/"
            "寬鬆對照（phantom幾乎只會落入涵蓋全體的100%組，檢定力天生較弱，"
            "不計入主判準，僅供參考）。"
        ),
        "per_feature": results,
        "summary": {
            "robust_features_main_criterion": robust_features,
            "sensitive_features_main_criterion": sensitive_features,
        },
    }
    out_path = RAW_DIR / "b4_feature_robustness_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"[B4] 完成，輸出已寫入 {out_path}")


if __name__ == "__main__":
    main()
