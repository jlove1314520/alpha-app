"""重構.B3：修三個方法論問題＋一個順手項，五題收尾（PENDING_QUEUE.md
「2026-09-19（重構.B3）」總司令原文，四項依序完成、一次回報）。

★一（最優先，可能翻轉Q5結論）：下市率被低估
    Q5「規模代理最小20%分位比值1.662最佳」的分母含下市率，但52%的
    delisted抽樣股票因fetch_error/no_data_found/price_too_short被排除，
    且下市集中在小型股——這個排除可能系統性壓低小型股分位的下市率，
    虛高比值。本檔案先分類這78檔（no_data_found清單另列、fetch_error
    在額度可用時重抓），再做「假設所有未解決的delisted都沒起飛且下市」
    的最壞情況敏感度分析，看1.662是否在上界下仍是最佳分位。

★二：Q4遺漏22%窗口（1,104/5,035），偏向delisted（78.6% vs 母體24.5%）
    改法：eps_yoy_pre與規模代理兩個分組欄位都增設「缺值」類，讓每個窗口
    都有歸屬，加總=5,035（詳見腳本內[自行裁量]說明，跟總司令原文「六格
    變九格」字面數字略有出入，因為規模代理本身也有136筆缺值，若不比照
    處理則加總對不上5,035這個更高優先的明確要求）。

★三：Q2排除方向跟結論同向（59.2%排除都是EPS為負/缺值的困境反轉股）
    新增PS（股價營收比）分解，對全部375個episode計算（不像EPS/PE分解
    只能用153個雙端EPS為正的episode）。用「log(P)=log(Rev_ttm)+
    log(P/Rev_ttm)」這個代數恆等式（見下方_rev_ttm_contrib()docstring），
    不需要流通股數資料（本管線已知限制：FinMind免費層無可靠股數欄位），
    營收恆正，虧損股一樣能分解，且是精確恆等式，沒有殘差項。

四（順手）：Q1改成股票層級（先前是窗口層級，已誠實揭露為限制）。
    「一年有多少比例的股票會翻倍」問的是股票，不是窗口——把同一檔股票
    在同一年出現的多個窗口去重，改成「該股票這一年是否至少有一次起飛」，
    再做母體加權。跟★一共用同一份「股票層級」底表（每檔股票一列），
    這份底表也是★一worst-case敏感度分析的基礎，見_build_stock_level_base()。

**資料重用、不重打API**：跟`multibagger_five_questions.py`同一份磁碟快取，
203檔ok股票的價格/EPS/營收已在`research/data/raw/*.parquet`，正常執行
不消耗FinMind額度。唯一會打API的是★一.1對60檔fetch_error delisted股票的
重抓嘗試，且已包在額度封鎖偵測與提前中止邏輯裡（見`_retry_fetch_error()`）。
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

from pit import month_revenue_pit
from universe import universe
from multibagger_attribution import (
    OUT_DIR, SAMPLE_PER_STRATUM, SAMPLE_SEED, WINDOW_MONTHS,
    _monthly_last, _eps_ttm_series, _asof_value, process_stock, stratified_sample,
)
from multibagger_five_questions import (
    CONTROL_GROUP_STRIDE_MONTHS, _all_windows, _weighted_rate, _process_stock_all_windows,
)

RAW_DIR = OUT_DIR
RATE_LIMIT_STATE = Path(__file__).resolve().parent.parent / "data" / "rate_limit_state.json"

# ---------------------------------------------------------------------------
# ★一.1：分類78檔未納入的delisted股票，額度可用時重抓fetch_error
# ---------------------------------------------------------------------------

def _load_skip_lists() -> dict[str, list[str]]:
    """從run_summary.json的skip_reasons_full切出delisted三類清單。"""
    with open(RAW_DIR / "run_summary.json", encoding="utf-8") as f:
        run_summary = json.load(f)
    srf = run_summary["skip_reasons_full"]
    delisted_skips = [e for e in srf if e.get("status") == "delisted"]
    out = {"fetch_error": [], "no_data_found": [], "price_too_short": []}
    for e in delisted_skips:
        r = e["skip_reason"]
        sid = e["stock_id"]
        if r.startswith("fetch_error"):
            out["fetch_error"].append(sid)
        elif r == "no_data_found":
            out["no_data_found"].append(sid)
        elif r == "price_too_short":
            out["price_too_short"].append(sid)
    for k in out:
        out[k].sort()
    return out


def _finmind_blocked() -> tuple[bool, float]:
    """回傳(是否封鎖中, 剩餘分鐘數)。查不到狀態檔／檔案正被其他排程行程
    同時寫入而暫時解析失敗，都視為未封鎖（保守：寧可嘗試被finmind_client
    自己的封鎖邏輯攔下，不自己臆測封鎖狀態不存在——這個檔案是多個排程
    共用、沒有檔案鎖的機器寫檔，讀到寫一半的瞬間屬於預期內的競態，不是
    真正的資料損毀，不應該讓本腳本整個崩潰）。"""
    if not RATE_LIMIT_STATE.exists():
        return False, 0.0
    try:
        with open(RATE_LIMIT_STATE, encoding="utf-8") as f:
            d = json.load(f)
    except json.JSONDecodeError:
        return False, 0.0
    fm = d.get("sources", {}).get("finmind", {})
    bu = fm.get("blocked_until")
    now = time.time()
    if bu and bu > now:
        return True, (bu - now) / 60.0
    return False, 0.0


def _retry_fetch_error(fetch_error_ids: list[str], delist_map: dict[str, str]) -> dict:
    """嘗試重抓fetch_error的delisted股票。額度封鎖中就直接跳過，不空等；
    重抓過程中一旦再度撞到RuntimeError（代表額度又被封鎖），立刻停止整批，
    不繼續消耗額度、也不影響其餘三項的執行。"""
    blocked, remaining_min = _finmind_blocked()
    if blocked:
        return {
            "attempted": False,
            "reason": f"額度封鎖中，剩餘約{remaining_min:.1f}分鐘，本輪跳過重抓",
            "recovered_stock_ids": [], "still_failed_stock_ids": fetch_error_ids,
        }
    recovered, still_failed = [], []
    stopped_early = False
    for i, sid in enumerate(fetch_error_ids):
        blocked_now, _ = _finmind_blocked()
        if blocked_now:
            stopped_early = True
            still_failed.extend(fetch_error_ids[i:])
            break
        try:
            result = process_stock(sid, "delisted", delist_map.get(sid))
            if "skip_reason" in result:
                still_failed.append(sid)
            else:
                recovered.append(sid)
        except RuntimeError:
            stopped_early = True
            still_failed.extend(fetch_error_ids[i:])
            break
        except Exception:
            still_failed.append(sid)
    return {
        "attempted": True, "stopped_early_due_to_quota": stopped_early,
        "recovered_stock_ids": recovered, "still_failed_stock_ids": still_failed,
    }


# ---------------------------------------------------------------------------
# ★一.2/四：股票層級底表（同時餵Q1股票層級與Q5最壞情況敏感度分析）
# ---------------------------------------------------------------------------

def _load_strata_info() -> dict:
    with open(RAW_DIR / "five_questions_result.json", encoding="utf-8") as f:
        prior = json.load(f)
    return prior["sample_strata_info"]


def _build_combined_windows_with_recovered(recovered_delisted_ids: list[str]) -> pd.DataFrame:
    """★一.1後續：把重抓成功的delisted股票併入全窗口對照組資料集，補上
    population_weight/outcome/is_delisted欄位（跟`multibagger_five_
    questions.py::main()`同一套邏輯），回傳合併後的完整df並落地成
    `all_windows_stride6m_recovered.csv`（gitignored，可重現）。population_
    weight是抽樣設計權重（母體佔比/抽樣佔比），不隨每一層實際成功抓到
    幾檔而變動，所以新併入的股票沿用同一個delisted層權重即可，不需要
    重新計算整批權重。"""
    from multibagger_attribution import MOONSHOT_THRESHOLD, CONTROL_THRESHOLD

    base = pd.read_csv(RAW_DIR / "all_windows_stride6m.csv")
    strata_info = _load_strata_info()
    pop_weight = {k: v["population_weight"] for k, v in strata_info.items()}

    new_rows = []
    for sid in recovered_delisted_ids:
        new_rows.extend(_process_stock_all_windows(sid, "delisted"))
    new_df = pd.DataFrame(new_rows)
    if not new_df.empty:
        new_df["population_weight"] = pop_weight["delisted"]
        new_df["outcome"] = np.select(
            [new_df["window_return"] >= MOONSHOT_THRESHOLD, new_df["window_return"] < CONTROL_THRESHOLD],
            ["moonshot", "control"], default="middle",
        )
        new_df["is_delisted"] = 1.0

    combined = pd.concat([base, new_df], ignore_index=True) if not new_df.empty else base
    combined.to_csv(RAW_DIR / "all_windows_stride6m_recovered.csv", index=False)
    return combined


def _build_stock_level_base(windows_df: pd.DataFrame | None = None) -> tuple[pd.DataFrame, dict]:
    """每檔「ok」股票一列：status、規模代理（該股票所有窗口avg_trading_
    money_20d_pre的中位數，作為單一股票層級規模proxy）、has_moonshot
    （該股票在樣本觀察窗內是否至少一次outcome=="moonshot"）、
    population_weight。回傳(df, strata_info)。`windows_df`可傳入合併過
    重抓股票的版本，預設讀原始`all_windows_stride6m.csv`。

    [自行裁量] 規模代理用「該股票所有窗口的中位數」而非單一時間點，因為
    同一檔股票在不同時間點liquidity會變動，中位數是對「這檔股票在觀察期
    內的典型規模」較穩健的代表值，且跟Q4/Q5原本window層級用的欄位
    （avg_trading_money_20d_pre）同源，語意上一致。
    """
    df = windows_df if windows_df is not None else pd.read_csv(RAW_DIR / "all_windows_stride6m.csv")
    strata_info = _load_strata_info()
    pop_weight = {k: v["population_weight"] for k, v in strata_info.items()}

    g = df.groupby("stock_id", as_index=False).agg(
        status=("status", "first"),
        size_proxy=("avg_trading_money_20d_pre", "median"),
        has_moonshot=("outcome", lambda s: bool((s == "moonshot").any())),
    )
    g["population_weight"] = g["status"].map(pop_weight).astype(float)
    return g, strata_info


def _q5_from_stock_table(stock_df: pd.DataFrame, size_col: str = "size_proxy") -> pd.DataFrame:
    """給定股票層級底表（含size_col/has_moonshot/is_delisted/population_weight），
    按規模代理分位門檻計算起飛率/下市率/比值，回傳跟原Q5同樣結構的表。"""
    has_sz = stock_df[size_col].notna()
    sz_valid = stock_df.loc[has_sz, size_col]
    rows = []
    for pct in (20, 40, 60, 80, 100):
        cutoff = sz_valid.quantile(pct / 100.0)
        sub = stock_df[has_sz & (stock_df[size_col] <= cutoff)]
        if sub.empty:
            continue
        w = sub["population_weight"]
        moon_rate = _weighted_rate(sub["has_moonshot"], w)
        delist_rate = _weighted_rate(sub["is_delisted"] == 1, w)
        rows.append({
            "規模代理分位門檻_百分位": pct, "n_stocks_raw": len(sub),
            "起飛率_股票層級_母體加權_pct": round(100 * moon_rate, 2) if moon_rate is not None else None,
            "下市率_股票層級_母體加權_pct": round(100 * delist_rate, 2) if delist_rate is not None else None,
            "起飛率_下市率_比值": round(moon_rate / delist_rate, 3)
                if moon_rate is not None and delist_rate not in (None, 0) else None,
        })
    return pd.DataFrame(rows)


def _q5_worst_case_sensitivity(stock_df: pd.DataFrame, strata_info: dict,
                                unresolved_delisted_ids: list[str]) -> dict:
    """★一.2/★一.3：假設所有未解決的delisted股票「沒起飛且下市」，且
    （最壞情況，也是壓垮1.662結論所需的最保守假設）規模比樣本中任何已觀察
    股票都小——因此會被計入全部5個累計分位門檻（20/40/60/80/100皆含），
    重算Q5，比較20%分位比值是否仍是最佳。

    [自行裁量] 「規模比任何已觀察股票都小」是刻意選的最壞假設，不是
    估計值：我們對這78檔真實規模一無所知，但總司令原文自己指出「下市
    集中在小型股」，把它們全部放進最小分位是讓1.662這個結論接受最不利
    的檢驗，若在這個上界下仍成立，才有資格說「結論穩健」。
    """
    base = stock_df.copy()
    base["is_delisted"] = (base["status"] == "delisted").astype(float)
    original_q5 = _q5_from_stock_table(base)

    delisted_weight = strata_info["delisted"]["population_weight"]
    # 用「比已觀察最小值再小1」而非-np.inf：pandas quantile()對含inf的序列做
    # 線性內插時會算出inf-inf=NaN（實測踩到，20分位那列因此整列消失、被
    # sub.empty悄悄跳過），改用有限值才能讓quantile()正確算出「比所有phantom
    # 都小」的門檻，同時仍保證phantom落在全部5個累計分位裡。
    sentinel_size = float(base["size_proxy"].min(skipna=True)) - 1.0
    phantom_rows = []
    for sid in unresolved_delisted_ids:
        phantom_rows.append({
            "stock_id": sid, "status": "delisted",
            "size_proxy": sentinel_size,  # 比任何已觀察值都小，確保落在全部5個累計分位
            "has_moonshot": False, "is_delisted": 1.0,
            "population_weight": delisted_weight,
        })
    worst_case = pd.concat([base, pd.DataFrame(phantom_rows)], ignore_index=True)
    worst_case_q5 = _q5_from_stock_table(worst_case)

    def _best_pct(table: pd.DataFrame) -> dict | None:
        valid = table.dropna(subset=["起飛率_下市率_比值"])
        if valid.empty:
            return None
        row = valid.loc[valid["起飛率_下市率_比值"].idxmax()]
        return {"規模代理分位門檻_百分位": int(row["規模代理分位門檻_百分位"]),
                "比值": float(row["起飛率_下市率_比值"])}

    best_original = _best_pct(original_q5)
    best_worst_case = _best_pct(worst_case_q5)
    conclusion_survives = (
        best_original is not None and best_worst_case is not None
        and best_original["規模代理分位門檻_百分位"] == best_worst_case["規模代理分位門檻_百分位"]
    )
    return {
        "n_phantom_delisted_added": len(phantom_rows),
        "q5_original_stock_level": original_q5.to_dict(orient="records"),
        "q5_worst_case": worst_case_q5.to_dict(orient="records"),
        "best_percentile_original": best_original,
        "best_percentile_worst_case": best_worst_case,
        "conclusion_survives_worst_case": conclusion_survives,
    }


# ---------------------------------------------------------------------------
# ★二：Q4改成規模代理(含缺值)×eps_yoy_sign(含缺值)
# ---------------------------------------------------------------------------

def _q4_with_missing_category() -> pd.DataFrame:
    df = pd.read_csv(RAW_DIR / "all_windows_stride6m.csv")
    n_total = len(df)

    has_liq = df["avg_trading_money_20d_pre"].notna()
    liq_valid = df.loc[has_liq, "avg_trading_money_20d_pre"]
    size_bins = liq_valid.quantile([0, 1 / 3, 2 / 3, 1.0]).to_numpy().copy()
    size_bins[0] -= 1.0
    df["size_tercile"] = "缺值(規模代理)"
    df.loc[has_liq, "size_tercile"] = pd.cut(
        liq_valid, bins=size_bins, labels=["小(規模代理)", "中(規模代理)", "大(規模代理)"]
    ).astype(str)

    df["eps_yoy_sign"] = np.select(
        [df["eps_yoy_pre"].isna(), df["eps_yoy_pre"] >= 0],
        ["缺值(EPS年增)", "EPS年增為正"], default="EPS年增為負",
    )

    rows = []
    for (sz, sign), g in df.groupby(["size_tercile", "eps_yoy_sign"], observed=True):
        w = g["population_weight"]
        rows.append({
            "size_tercile": sz, "eps_yoy_sign": sign, "n_windows_raw": len(g),
            "起飛率_raw_pct": round(100 * (g["outcome"] == "moonshot").mean(), 2),
            "平庸率_raw_pct": round(100 * (g["outcome"] == "middle").mean(), 2),
            "下市率_raw_pct": round(100 * g["is_delisted"].mean(), 2),
            "起飛率_母體加權_pct": round(100 * _weighted_rate(g["outcome"] == "moonshot", w), 2),
            "平庸率_母體加權_pct": round(100 * _weighted_rate(g["outcome"] == "middle", w), 2),
            "下市率_母體加權_pct": round(100 * _weighted_rate(g["is_delisted"] == 1, w), 2),
        })
    table = pd.DataFrame(rows).sort_values(["size_tercile", "eps_yoy_sign"]).reset_index(drop=True)
    n_sum = int(table["n_windows_raw"].sum())
    assert n_sum == n_total, f"Q4九宮格加總{n_sum}!= 總樣本{n_total}，有窗口漏歸屬"
    return table


# ---------------------------------------------------------------------------
# ★三：PS（股價營收比）分解，對全部375個episode
# ---------------------------------------------------------------------------

def _rev_ttm_series(rev: pd.DataFrame) -> pd.DataFrame:
    """TTM營收（近12個月加總），帶pit_date，跟_eps_ttm_series()同構。"""
    if rev.empty or "revenue" not in rev.columns:
        return pd.DataFrame(columns=["pit_date", "rev_ttm"])
    r = rev.sort_values("pit_date").reset_index(drop=True)
    r["rev_ttm"] = r["revenue"].rolling(12, min_periods=12).sum()
    out = r.dropna(subset=["rev_ttm"])[["pit_date", "rev_ttm"]].reset_index(drop=True)
    return out


def _ps_decompose_episode(price: pd.DataFrame, rev_ttm: pd.DataFrame,
                           window_start: str, month_end: str) -> dict:
    """log(P_end/P_start) = log(Rev_ttm_end/Rev_ttm_start) + log((P_end/Rev_ttm_end)/(P_start/Rev_ttm_start))
    是代數恆等式（兩邊展開後相消），不需要流通股數，營收恆正，不像EPS
    分解需要雙端為正才能取log——這正是★三要解決的問題。

    已知限制（跟現有EPS/PE分解的殘差同一種限制，非新引入）：這裡的
    `P/Rev_ttm`不是教科書定義的「每股營收」對應的真PS比值（真PS比值=
    P/(Rev_ttm/股數)），兩者相差一個股數的比例——若episode期間股數
    有變動（現金增資/私募等），這個變動會混進log_ps_contrib項，
    無法獨立拆分。但這不影響log_rev_contrib（純營收成長，股數無關），
    且跟現有EPS/PE分解一樣誠實揭露、不假裝精確。
    """
    close_start_row = price[pd.to_datetime(price["date"]) <= pd.Timestamp(window_start)]
    close_end_row = price[pd.to_datetime(price["date"]) <= pd.Timestamp(month_end)]
    if close_start_row.empty or close_end_row.empty:
        return {"log_rev_contrib": np.nan, "log_ps_contrib": np.nan, "log_price_return_raw_ps": np.nan}
    close_start = float(close_start_row["close"].iloc[-1])
    close_end = float(close_end_row["close"].iloc[-1])
    rev_start = _asof_value(rev_ttm, "rev_ttm", pd.Timestamp(window_start))
    rev_end = _asof_value(rev_ttm, "rev_ttm", pd.Timestamp(month_end))
    if pd.isna(rev_start) or pd.isna(rev_end) or rev_start <= 0 or rev_end <= 0 or close_start <= 0:
        return {"log_rev_contrib": np.nan, "log_ps_contrib": np.nan, "log_price_return_raw_ps": np.nan}
    log_price_return_raw = float(np.log(close_end / close_start))
    log_rev_contrib = float(np.log(rev_end / rev_start))
    log_ps_contrib = log_price_return_raw - log_rev_contrib
    return {
        "log_rev_contrib": log_rev_contrib, "log_ps_contrib": log_ps_contrib,
        "log_price_return_raw_ps": log_price_return_raw,
    }


def _q2_ps_decomposition() -> pd.DataFrame:
    from adjust import adjusted_price_series  # 延遲載入，跟multibagger_five_questions.py一致

    episodes = pd.read_csv(RAW_DIR / "moonshot_windows_sample.csv")
    out_rows = []
    price_cache: dict[str, pd.DataFrame] = {}
    revttm_cache: dict[str, pd.DataFrame] = {}
    for _, ep in episodes.iterrows():
        sid = str(ep["stock_id"])
        if sid not in price_cache:
            try:
                price_cache[sid] = adjusted_price_series(sid)
                revttm_cache[sid] = _rev_ttm_series(month_revenue_pit(sid))
            except Exception:
                price_cache[sid] = pd.DataFrame()
                revttm_cache[sid] = pd.DataFrame()
        price = price_cache[sid]
        rev_ttm = revttm_cache[sid]
        if price.empty:
            ps = {"log_rev_contrib": np.nan, "log_ps_contrib": np.nan, "log_price_return_raw_ps": np.nan}
        else:
            ps = _ps_decompose_episode(price, rev_ttm, ep["window_start"], ep["month_end"])
        out_rows.append({
            "stock_id": sid, "window_start": ep["window_start"], "month_end": ep["month_end"],
            "log_eps_contrib": ep["log_eps_contrib"], "log_pe_contrib": ep["log_pe_contrib"],
            **ps,
        })
    return pd.DataFrame(out_rows)


# ---------------------------------------------------------------------------
# 四：Q1股票層級（去重＋母體加權）
# ---------------------------------------------------------------------------

def _q1_stock_level(stock_df_all_windows: pd.DataFrame) -> dict:
    """跟原本窗口層級不同：先按(stock_id, year)去重（該股票該年只要有一次
    起飛就算1），再做母體加權，回答「一年有多少比例的股票會翻倍」。"""
    df = stock_df_all_windows.copy()
    df["year"] = pd.to_datetime(df["month_end"]).dt.year
    by_stock_year = df.groupby(["stock_id", "status", "population_weight", "year"], as_index=False).agg(
        has_moonshot_this_year=("outcome", lambda s: bool((s == "moonshot").any()))
    )
    out = {}
    for y in sorted(by_stock_year["year"].unique()):
        g = by_stock_year[by_stock_year["year"] == y]
        w = g["population_weight"]
        hit_w = float(g.loc[g["has_moonshot_this_year"], "population_weight"].sum())
        denom_w = float(w.sum())
        out[int(y)] = {
            "n_stocks_observed_raw": int(len(g)),
            "n_stocks_moonshot_raw": int(g["has_moonshot_this_year"].sum()),
            "moonshot_stock_weight_sum": round(hit_w, 3),
            "all_stock_weight_sum": round(denom_w, 3),
            "weighted_rate_pct": round(100 * hit_w / denom_w, 3) if denom_w else None,
        }
    return out


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    print("[v2] ===== ★一：下市率被低估，worst-case敏感度分析 =====")
    skip_lists = _load_skip_lists()
    print(f"[v2] delisted 78檔未納入：fetch_error={len(skip_lists['fetch_error'])}, "
          f"no_data_found={len(skip_lists['no_data_found'])}, price_too_short={len(skip_lists['price_too_short'])}")
    print(f"[v2] no_data_found清單（另列，非fetch_error不重抓）：{skip_lists['no_data_found']}")

    uni = universe()
    delist_map = dict(zip(uni["stock_id"], uni["delist_date"]))
    retry_result = _retry_fetch_error(skip_lists["fetch_error"], delist_map)
    print(f"[v2] fetch_error重抓結果：{json.dumps(retry_result, ensure_ascii=False)}")

    recovered_ids = retry_result.get("recovered_stock_ids", [])
    if recovered_ids:
        # 重抓成功的股票併入全窗口對照組資料集（重跑_process_stock_all_windows
        # 補上control-group窗口，不是只有process_stock()的episode資料），
        # 讓stock_df/Q1都反映補齊後的下市股樣本，不是只把它們從worst-case
        # 清單移除卻不提供真實資料。
        windows_df = _build_combined_windows_with_recovered(recovered_ids)
        print(f"[v2] {len(recovered_ids)}檔重抓成功已併入全窗口資料集，"
              f"新增{len(windows_df) - 5035}個窗口，總窗口數={len(windows_df)}")
    else:
        windows_df = pd.read_csv(RAW_DIR / "all_windows_stride6m.csv")

    stock_df, strata_info = _build_stock_level_base(windows_df)
    # worst-case清單＝所有原本78檔未納入的，扣掉這次重抓成功恢復的——恢復的
    # 已經用真實資料併入stock_df，不再需要當成phantom計入worst-case。
    all_78 = skip_lists["fetch_error"] + skip_lists["no_data_found"] + skip_lists["price_too_short"]
    recovered = set(recovered_ids)
    unresolved = [sid for sid in all_78 if sid not in recovered]
    print(f"[v2] 重抓後仍未解決的delisted股票數：{len(unresolved)}（原78檔）")
    q5_sensitivity = _q5_worst_case_sensitivity(stock_df, strata_info, unresolved)
    print(f"[v2] Q5 worst-case：original best={q5_sensitivity['best_percentile_original']}, "
          f"worst_case best={q5_sensitivity['best_percentile_worst_case']}, "
          f"結論存活={q5_sensitivity['conclusion_survives_worst_case']}")

    print("[v2] ===== ★二：Q4改成規模代理(缺值)×eps_yoy_sign(缺值) =====")
    q4_table = _q4_with_missing_category()
    print(f"[v2] Q4新表（加總={int(q4_table['n_windows_raw'].sum())}）：\n{q4_table.to_string(index=False)}")

    print("[v2] ===== ★三：PS分解，全部375個episode =====")
    ps_table = _q2_ps_decomposition()
    n_ps_valid = ps_table["log_ps_contrib"].notna().sum()
    n_eps_valid = ps_table["log_eps_contrib"].notna().sum()
    print(f"[v2] PS分解可用episode數={n_ps_valid}/375，原EPS/PE分解可用數={n_eps_valid}/375")
    print(f"[v2] PS分解中位數：log_rev_contrib={ps_table['log_rev_contrib'].median():.4f}, "
          f"log_ps_contrib={ps_table['log_ps_contrib'].median():.4f}")
    both_valid = ps_table.dropna(subset=["log_eps_contrib", "log_pe_contrib", "log_rev_contrib", "log_ps_contrib"])
    print(f"[v2] 兩套分解都有值的episode數={len(both_valid)}（交集，用於比對一致性）")

    print("[v2] ===== 四：Q1改成股票層級 =====")
    q1_stock_level = _q1_stock_level(windows_df.assign(
        population_weight=lambda d: d["status"].map(
            {k: v["population_weight"] for k, v in strata_info.items()}).astype(float)
    ))
    print(f"[v2] Q1股票層級逐年加權起飛率：{json.dumps(q1_stock_level, ensure_ascii=False)}")

    out = {
        "generated_from": "multibagger_five_questions_v2.py（重構.B3）",
        "star1_delisted_undercount": {
            "skip_lists": skip_lists,
            "retry_fetch_error_result": retry_result,
            "n_recovered_integrated_into_windows": len(recovered_ids),
            "n_total_windows_after_recovery": len(windows_df),
            "unresolved_stock_ids_used_in_worst_case": unresolved,
            "q5_sensitivity": q5_sensitivity,
        },
        "star2_q4_with_missing_category": q4_table.to_dict(orient="records"),
        "star3_q2_ps_decomposition": {
            "n_episodes_total": len(ps_table),
            "n_ps_valid": int(n_ps_valid), "n_eps_pe_valid": int(n_eps_valid),
            "log_rev_contrib_median": float(ps_table["log_rev_contrib"].median()),
            "log_ps_contrib_median": float(ps_table["log_ps_contrib"].median()),
            "both_decompositions_valid_n": len(both_valid),
        },
        "item4_q1_stock_level": q1_stock_level,
    }
    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / "five_questions_result_v2.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    ps_table.to_csv(OUT_DIR / "ps_decomposition_375episodes.csv", index=False)
    q4_table.to_csv(OUT_DIR / "q4_table_12cells.csv", index=False)
    print("[v2] 完成，輸出已寫入 research/multibagger_raw/")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
