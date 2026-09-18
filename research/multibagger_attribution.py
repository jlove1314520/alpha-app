"""飆股歸因分解（衛星倉·描述性研究，非策略）——重構.B。

背景見 PENDING_QUEUE.md「2026-09-18（續3）總司令裁示【新方向·衛星倉研究】」。
本檔案回答總司令列出的五題，全程 PIT-safe、只用 TRAIN+VAL（<=VAL_END，
holdout 不碰——沿用 adjust.adjusted_price_series()/pit.py 既有的 load_dev()
截斷，不另外重造機制）。**這一輪只做描述性分析，不生選股規則。**

「起飛事件」定義：任一個股在任一 12 個月窗口內（月頻滾動，即每月底往回看
12 個月）還原權息報酬 >= MOONSHOT_THRESHOLD（100%）。

資料來源與既有模組的對應（避免重造輪子，也避免繞過既有 PIT 保護）：
- 宇宙（含下市股，分母靈魂）：universe.universe()
- 還原權息價格（已 load_dev() 截斷在 VAL_END）：adjust.adjusted_price_series()
- EPS（PIT，申報日+45天）：pit.quarterly_pit()
- 月營收 YoY（PIT）：pit.month_revenue_pit()
- 三大法人／相對強度／低波動等既有因子：factors.prepare_factors()
- 市值分位：FinMind 免費層沒有 TaiwanStockMarketValue（付費），沿用
  score_v2.py 既有慣例——用 20 日均成交金額當規模/流動性替代指標，
  不是真市值，本檔輸出會誠實標註這個限制，不偽裝成真市值。

已知限制（如實揭露，不是遺漏）：
- 歸因分解（第2題）只能拆成「EPS成長貢獻」+「PE變化貢獻」兩項嚴格對數
  報酬恆等式（dlogPrice_pe = dlogEPS_ttm + dlogPE_ttm，PE_ttm 用原始
  （非還原權息）收盤價算，因為真實市場 P/E 用的是原始價格；還原權息
  報酬另外單獨呈現，兩者差額標為「股利與其他調整殘差」）。commander
  原文要求三項（EPS成長/PE變化/股數變化），但 FinMind 免費層的
  TaiwanStockFinancialStatements 沒有可靠的流通股數欄位可以獨立驗證，
  勉強拆出第三項等於杜撰數字——按七之三節工程紀律「加總對不上，修在
  產生資料的地方，不是在稽核裡調算法讓它通過」的精神，這裡選擇誠實
  只交兩項嚴格恆等式，並把「股數變化」列為待下一輪補資料源後再拆的
  已知缺口，不是忽略。
- 這是小樣本驗證輪（active/delisted各SAMPLE_PER_STRATUM檔，2026-09-18
  改為分層抽樣，見stratified_sample()），不是全宇宙——照裁示原文「先跑
  一個小樣本驗證管線正確，再放全宇宙，不要一次賭全量」執行，全宇宙是
  下一輪的工作。
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from adjust import adjusted_price_series
from pit import quarterly_pit, month_revenue_pit
from universe import universe

MOONSHOT_THRESHOLD = 1.0  # 12個月還原權息報酬 >= 100%
CONTROL_THRESHOLD = 0.20  # 對照組上限：後續12個月報酬 < 20%
WINDOW_MONTHS = 12
PRE_WINDOW_MONTHS = 12  # 起漲前特徵觀察窗（含"起漲前250日報酬"另計）
# 2026-09-18（Cowork【重構.B續·先別放棄】二）：改成分層抽樣（active/
# delisted各抽SAMPLE_PER_STRATUM檔），取代舊版對母體單純隨機抽樣的
# SAMPLE_SIZE——原因見stratified_sample()docstring。環境變數
# MULTIBAGGER_SMOKE_SIZE沿用同一個名字但語意變成「每層抽幾檔」
# （例如設10代表active 10檔+delisted 10檔=20檔），先確認程式碼邏輯
# 正確再放大到正式的150。
SAMPLE_PER_STRATUM = 150
import os
SAMPLE_PER_STRATUM = int(os.environ.get("MULTIBAGGER_SMOKE_SIZE", SAMPLE_PER_STRATUM))
OUT_DIR = Path(__file__).parent / "multibagger_raw"  # gitignored，見下方 main()


def _monthly_last(price: pd.DataFrame) -> pd.DataFrame:
    """月頻（每月最後一個交易日）還原權息收盤 + 原始收盤，供窗口報酬與PE計算。"""
    d = price.copy()
    d["date"] = pd.to_datetime(d["date"])
    d = d.set_index("date").sort_index()
    m = d.resample("ME").last()[["adj_close", "close"]].dropna(subset=["adj_close"])
    m = m.reset_index().rename(columns={"date": "month_end"})
    return m


def _find_moonshot_windows(monthly: pd.DataFrame) -> pd.DataFrame:
    """回傳「episode」（同一次上漲只算一筆事件），不是舊版的「window」。

    2026-09-18（Cowork【重構.B收成前必修】1修正）：舊版回傳每一個滿足
    12個月窗報酬>=100%的月份，一次上漲的整段持續期間（可能長達一兩年）
    每個月都各算一筆，20檔煙霧測試量到17檔跑進核心計算卻產生198個窗口
    （11.6筆/檔），會把起飛率灌水約一個數量級，且失敗案例不會產生連續
    窗口、成功案例會，等於分子被放大、分母沒有對應放大，是系統性偏誤
    不是噪音。

    規則：
    1. 上升緣偵測——只在「上個月不符合、這個月符合」時記一筆事件，該筆
       事件的 month_end/window_start/window_return 一律取「上升緣當月」
       的數值（這樣起漲前特徵才是真的在起漲前，不是漲勢中段）。
    2. 記完一筆後強制冷卻 WINDOW_MONTHS 個月：下一次上升緣要落在冷卻期
       結束之後才允許再記一筆，防止「達標→短暫拉回→立刻又達標」被算成
       兩次獨立事件。冷卻期從本筆事件的上升緣月份起算。
    3. 不丟掉「這次上漲維持了多久」這個資訊，額外記錄
       episode_length_months（達標連續了幾個月）與 peak_return（連續期間
       內最高的12個月滾動報酬），只是不重複計數成多筆事件。
    """
    cols = ["month_end", "window_start", "window_return",
            "episode_length_months", "peak_return", "window_start_idx"]
    if len(monthly) < WINDOW_MONTHS + 1:
        return pd.DataFrame(columns=cols)
    adj = monthly["adj_close"].to_numpy()
    ret = adj[WINDOW_MONTHS:] / adj[:-WINDOW_MONTHS] - 1.0
    ends = monthly["month_end"].to_numpy()[WINDOW_MONTHS:]
    starts = monthly["month_end"].to_numpy()[:-WINDOW_MONTHS]
    mask = ret >= MOONSHOT_THRESHOLD

    episodes = []
    n = len(mask)
    prev_true = False
    cooldown_until = -1  # 上升緣的索引 < 這個值就不得再記一筆
    i = 0
    while i < n:
        is_rising_edge = bool(mask[i]) and not prev_true
        if is_rising_edge and i >= cooldown_until:
            j = i
            while j + 1 < n and mask[j + 1]:
                j += 1
            episodes.append({
                "month_end": ends[i], "window_start": starts[i],
                "window_return": float(ret[i]),
                "episode_length_months": int(j - i + 1),
                "peak_return": float(ret[i:j + 1].max()),
                "window_start_idx": i,  # 對應monthly裡的列位置，供特徵取值定位用
            })
            cooldown_until = i + WINDOW_MONTHS
        prev_true = bool(mask[i])
        i += 1
    return pd.DataFrame(episodes, columns=cols)


def _eps_ttm_series(stock_id: str) -> pd.DataFrame:
    """TTM EPS（近四季加總），帶 pit_date。回傳 pit_date, eps_ttm 兩欄，已依 pit_date 排序去重。"""
    q = quarterly_pit(stock_id)
    if q.empty or "EPS" not in q.columns:
        return pd.DataFrame(columns=["pit_date", "eps_ttm"])
    q = q.sort_values("fiscal_period_end").reset_index(drop=True)
    q["eps_ttm"] = q["EPS"].rolling(4, min_periods=4).sum()
    out = q.dropna(subset=["eps_ttm"])[["pit_date", "eps_ttm"]].reset_index(drop=True)
    return out


def _asof_value(pit_df: pd.DataFrame, value_col: str, as_of_date: pd.Timestamp) -> float:
    """在 as_of_date 當天可得（pit_date <= as_of_date）的最新一筆數值。純函式，PIT-safe。"""
    if pit_df.empty:
        return np.nan
    avail = pit_df[pd.to_datetime(pit_df["pit_date"]) <= as_of_date]
    if avail.empty:
        return np.nan
    return float(avail.iloc[-1][value_col])


def _pre_window_features(price: pd.DataFrame, eps_ttm: pd.DataFrame, rev: pd.DataFrame,
                          monthly: pd.DataFrame, window_start_idx: int) -> dict:
    """起漲前特徵，第3題。

    2026-09-18（Cowork【重構.B收成前必修】2修正）：舊版直接用`window_start`
    當asof日期。去重疊之後`window_start`本身已經是正確的episode起點
    （不再是漲勢中段），但為了不踩「window_start當月的價格本身就是12個月
    報酬計算的分母」這條邊界、也為了讓「起漲前」在語意上更保守，特徵基準
    一律改成 **episode起點（window_start）的前一個月月底**，並用
    `feature_asof_date`欄位明文記錄實際取值日，方便事後稽核「這個特徵
    是哪一天算出來的」。`window_start_idx`是`_find_moonshot_windows()`
    回傳的、window_start在`monthly`裡的列位置，往前一列就是「前一個月
    月底」；index==0（資料一開始就達標，前面沒有更早的月份可取）時只能
    退回用window_start本身，這是資料邊界的誠實例外，不是bug。

    **PIT-safe不等於沒有前視，這是兩件事**：這裡每個數值查詢本身都用
    `_asof_value()`嚴格限制pit_date<=asof日期，是PIT-safe的；但如果
    asof日期這個「事件標記」本身選錯了（例如舊版誤用漲勢中段的月份），
    PIT-safe的查詢一樣會忠實地回傳「那個錯誤時間點當下可得的資料」，
    產生的特徵仍然是前視污染的——PIT-safe只保證「不會看到asof日期之後
    才公布的資料」，不保證asof日期本身選對了。
    """
    asof_idx = max(window_start_idx - 1, 0)
    asof_date = pd.Timestamp(monthly.iloc[asof_idx]["month_end"])

    eps0 = _asof_value(eps_ttm, "eps_ttm", asof_date)
    eps_prior = eps_ttm[pd.to_datetime(eps_ttm["pit_date"]) <= asof_date]
    eps_yoy = np.nan
    if len(eps_prior) >= 5 and eps0 not in (np.nan,):
        eps_1y_ago = float(eps_prior.iloc[-5]["eps_ttm"]) if len(eps_prior) >= 5 else np.nan
        if pd.notna(eps_1y_ago) and eps_1y_ago != 0:
            eps_yoy = eps0 / eps_1y_ago - 1.0
    rev_yoy = np.nan
    if not rev.empty and "revenue" in rev.columns:
        rv = rev[pd.to_datetime(rev["pit_date"]) <= asof_date].sort_values("pit_date")
        if len(rv) >= 4:
            rev_yoy = np.nan  # 月營收YoY另有現成因子，這裡小樣本輪先留白，不杜撰
    d = price.copy()
    d["date"] = pd.to_datetime(d["date"])
    pre = d[d["date"] <= asof_date].sort_values("date")
    ret_250d = np.nan
    if len(pre) > 250:
        p_now = pre["adj_close"].iloc[-1]
        p_250 = pre["adj_close"].iloc[-251]
        if pd.notna(p_now) and pd.notna(p_250) and p_250 != 0:
            ret_250d = float(p_now / p_250 - 1.0)
    pe0 = np.nan
    if pd.notna(eps0) and eps0 > 0 and len(pre) > 0:
        pe0 = float(pre["close"].iloc[-1] / eps0)
    liq20 = np.nan
    if "Trading_money" in pre.columns and len(pre) >= 20:
        liq20 = float(pre["Trading_money"].tail(20).mean())
    return {
        "feature_asof_date": str(asof_date.date()),
        "eps_ttm_pre": eps0, "eps_yoy_pre": eps_yoy, "pe_pre": pe0,
        "ret_250d_pre": ret_250d, "avg_trading_money_20d_pre": liq20,
    }


def process_stock(stock_id: str, status: str, delist_date) -> dict:
    """單檔股票的完整處理，任何一步失敗只回傳空殼＋錯誤標記，不外溢中斷其他股票
    （沿用 CLAUDE.md「錯誤隔離原則」，此處等價於逐檔 try/except）。

    2026-09-18（Cowork【重構.B續·先別放棄】一.4修正）：舊版`except Exception`
    把三種完全不同的狀況收斂成同一個`skip_reason`字串——`adjusted_price_
    series()`回空（yfinance＋FinMind都真的查無此檔，"沒有資料"）、回傳的
    資料筆數不足260天（"資料不足"）、`finmind_client.py::_fetch()`拋出
    `RuntimeError`（額度/冷卻/HTTP錯誤，"問不到"不是"問了沒有"——這是
    `_fetch()`自己docstring寫明的區分：「Raises RuntimeError if every
    retry fails -- callers should not silently treat a fetch failure as
    no data (that was the App's old bug pattern)」，研究管線不該重蹈這個
    老bug）。現在分開記錄：
    - `no_data_found`：兩個價格源都回空，真的查無此檔
    - `price_too_short`：有資料但筆數<260天
    - `fetch_error: ...`：`RuntimeError`（額度/冷卻/HTTP層級問題，不代表
      「沒有這檔資料」，只代表「這次問不到」）
    - `error: ...`：其他未預期例外（管線本身的bug）
    """
    try:
        price = adjusted_price_series(stock_id)
        if price.empty:
            return {"stock_id": stock_id, "status": status, "skip_reason": "no_data_found"}
        if len(price) < 260:
            return {"stock_id": stock_id, "status": status, "skip_reason": "price_too_short"}
        monthly = _monthly_last(price)
        windows = _find_moonshot_windows(monthly)
        eps_ttm = _eps_ttm_series(stock_id)
        rev = month_revenue_pit(stock_id)

        moonshot_rows = []
        for _, w in windows.iterrows():
            # 2026-09-18修正：feat（起漲前描述性特徵）現在錨定在window_start
            # 「前一個月月底」，跟這裡歸因分解要用的「window_start當月」
            # eps_start/close_start是兩件事、兩個不同的asof日期，不能共用
            # 同一個值——分解用的eps_start必須跟close_start同一天，否則
            # log_eps_contrib會摻進一個月的時間差雜訊。
            feat = _pre_window_features(price, eps_ttm, rev, monthly, int(w["window_start_idx"]))
            eps_end = _asof_value(eps_ttm, "eps_ttm", pd.Timestamp(w["month_end"]))
            eps_start = _asof_value(eps_ttm, "eps_ttm", pd.Timestamp(w["window_start"]))
            close_end = float(monthly.loc[monthly["month_end"] == w["month_end"], "close"].iloc[0])
            close_start_row = price[pd.to_datetime(price["date"]) <= pd.Timestamp(w["window_start"])]
            close_start = float(close_start_row["close"].iloc[-1]) if len(close_start_row) else np.nan
            pe_end = close_end / eps_end if pd.notna(eps_end) and eps_end > 0 else np.nan
            pe_start = close_start / eps_start if pd.notna(eps_start) and eps_start > 0 and pd.notna(close_start) else np.nan
            log_eps_contrib = np.log(eps_end / eps_start) if pd.notna(eps_end) and pd.notna(eps_start) and eps_end > 0 and eps_start > 0 else np.nan
            log_pe_contrib = np.log(pe_end / pe_start) if pd.notna(pe_end) and pd.notna(pe_start) and pe_end > 0 and pe_start > 0 else np.nan
            log_price_return_raw = np.log(close_end / close_start) if pd.notna(close_start) and close_start > 0 else np.nan
            residual = (log_price_return_raw - (log_eps_contrib if pd.notna(log_eps_contrib) else 0)
                        - (log_pe_contrib if pd.notna(log_pe_contrib) else 0)) if pd.notna(log_price_return_raw) else np.nan
            moonshot_rows.append({
                "stock_id": stock_id, "month_end": str(w["month_end"])[:10],
                "window_start": str(w["window_start"])[:10],
                "window_return_total": float(w["window_return"]),
                "episode_length_months": int(w["episode_length_months"]),
                "peak_return": float(w["peak_return"]),
                "log_eps_contrib": log_eps_contrib, "log_pe_contrib": log_pe_contrib,
                "log_residual_dividend_and_other": residual,
                **feat,
            })

        return {
            "stock_id": stock_id, "status": status,
            "delist_date": str(delist_date) if pd.notna(delist_date) else None,
            "n_months": len(monthly), "n_moonshot_windows": len(windows),
            "moonshot_rows": moonshot_rows,
        }
    except RuntimeError as e:
        # finmind_client.py的_fetch()/_rate_limit_wait_or_raise()專門用RuntimeError
        # 表達「這次問不到」（額度用盡/冷卻中/HTTP 4xx等）——這不是「沒有這檔資料」，
        # 是「這次沒辦法問」，兩者混在一起會讓存活者偏誤的判定失真（見上方docstring）。
        return {"stock_id": stock_id, "status": status, "skip_reason": f"fetch_error: {e}"}
    except Exception as e:  # noqa: BLE001 -- 逐檔隔離，見上方 docstring
        return {"stock_id": stock_id, "status": status, "skip_reason": f"error: {e}"}


SAMPLE_SEED = 42  # 固定種子，確保每次重跑抽到同一組樣本（可重現）


def _two_proportion_ztest(skip_a: int, n_a: int, skip_b: int, n_b: int) -> tuple[float | None, float | None]:
    """兩樣本skip率的pooled proportion z檢定，回傳(z, 雙尾p值)。
    任一組n<5時回傳(None, None)，誠實標「樣本太小無法檢定」而非硬算一個
    不穩定的p值。"""
    if n_a < 5 or n_b < 5:
        return None, None
    p_a, p_b = skip_a / n_a, skip_b / n_b
    p_pool = (skip_a + skip_b) / (n_a + n_b)
    se = (p_pool * (1 - p_pool) * (1 / n_a + 1 / n_b)) ** 0.5
    if se == 0:
        return None, None
    z = (p_b - p_a) / se
    p_value = float(2 * (1 - stats.norm.cdf(abs(z))))
    return float(z), p_value


def _skip_category(skip_reason: str) -> str:
    """把完整skip_reason字串（可能帶落落長的錯誤訊息）正規化成四類之一，
    供分類統計用——`skip_reason_distribution`裡放的是這個，完整原始訊息
    另外保留在`errors`本身，不會丟失，只是分類統計不會被錯誤訊息的
    細節文字打散成幾百個各出現1次的key。"""
    if skip_reason == "no_data_found":
        return "no_data_found"
    if skip_reason == "price_too_short":
        return "price_too_short"
    if skip_reason.startswith("fetch_error:"):
        return "fetch_error"
    return "other_error"


def _skip_reason_category_summary(errors: list[dict], n_examples: int = 5) -> dict:
    """2026-09-18（Cowork【重構.B續·先別放棄】一.1）：全體174筆skip（不分
    active/delisted）依四類分別給檔數、佔比，外加每類的stock_id範例
    （供一.2挑delisted代號逐一驗證用，不用另外重新掃一次）。"""
    total = len(errors)
    by_cat: dict[str, list[dict]] = {}
    for e in errors:
        by_cat.setdefault(_skip_category(e["skip_reason"]), []).append(e)
    summary = {}
    for cat, items in sorted(by_cat.items(), key=lambda kv: -len(kv[1])):
        summary[cat] = {
            "count": len(items),
            "pct_of_all_skips": round(100.0 * len(items) / total, 1) if total else None,
            "example_stock_ids": [it["stock_id"] for it in items[:n_examples]],
            "example_delisted_stock_ids": [it["stock_id"] for it in items if it["status"] == "delisted"][:n_examples],
        }
    return summary


def _survivorship_skip_breakdown(sample: pd.DataFrame, results: list[dict], errors: list[dict]) -> dict:
    """2026-09-18（Cowork【重構.B收成前必修】3）：active/delisted兩組各自的
    總檔數/成功/skip率/skip_reason分布，外加active vs delisted skip率的
    顯著性檢定——這個數字比任何起飛率/命中率結論都重要，因為它決定命中率
    要打幾折，五題裡沒回答這個之前不准把任何數字寫進結論。

    2026-09-18（續·先別放棄）：`skip_reason_distribution`改用`_skip_category()`
    正規化過的四類當key，不是原始完整錯誤訊息字串（後者每筆RuntimeError
    訊息細節不同，會被打散成幾十個各出現1次的key，看不出類別佔比）。
    """
    breakdown = {}
    for status_val in sorted(sample["status"].unique()):
        total = int((sample["status"] == status_val).sum())
        ok_n = sum(1 for r in results if r["status"] == status_val)
        skip_n = sum(1 for e in errors if e["status"] == status_val)
        reasons: dict[str, int] = {}
        for e in errors:
            if e["status"] == status_val:
                cat = _skip_category(e["skip_reason"])
                reasons[cat] = reasons.get(cat, 0) + 1
        breakdown[status_val] = {
            "total": total, "ok": ok_n, "skip": skip_n,
            "skip_rate_pct": round(100.0 * skip_n / total, 1) if total else None,
            "skip_reason_distribution": reasons,
        }
    if "active" in breakdown and "delisted" in breakdown:
        a, d = breakdown["active"], breakdown["delisted"]
        z, p = _two_proportion_ztest(a["skip"], a["total"], d["skip"], d["total"])
        breakdown["_active_vs_delisted_test"] = {
            "method": "two-proportion pooled z-test（雙尾）",
            "z": z, "p_value": p,
            "delisted_skip_rate_significantly_higher":
                (p is not None and p < 0.05 and d["skip_rate_pct"] > a["skip_rate_pct"]),
        }
    return breakdown


def stratified_sample(normal_stock: pd.DataFrame, per_stratum: int, seed: int) -> tuple[pd.DataFrame, dict]:
    """2026-09-18（Cowork【重構.B續·先別放棄】二）：active/delisted各抽
    `per_stratum`檔（同一固定種子），不是對母體單純隨機抽樣。

    **為什麼要分層**：母體裡delisted只佔約7%，300檔單純隨機抽樣期望值只有
    約21~22檔delisted（實測跑出14檔），而五題裡的Q4對照組（特徵相似但
    沒起飛、含下市）正是整份研究的靈魂，那一格永遠湊不出足夠樣本。

    **分層之後基準機率要用權重還原**：分層樣本裡delisted被人為過抽（例如
    分層後可能佔50%，母體只有7.32%），任何要推回「母體」層級的統計量
    （例如第1題的逐年基準機率）必須乘以`population_weight`欄位（母體
    佔比/分層樣本佔比）加權平均，不能直接拿分層樣本的比例當母體比例
    ——這裡只負責回傳分層資訊與權重，加權計算由呼叫端在需要時自行套用，
    這支只保證資訊「不遺失」，不擅自在這裡就把權重套用到本來就是描述性
    的中間輸出。
    """
    strata = {}
    for status_val in ("active", "delisted"):
        pool = normal_stock[normal_stock["status"] == status_val]
        n_pick = min(per_stratum, len(pool))
        strata[status_val] = pool.sample(n=n_pick, random_state=seed).reset_index(drop=True) if n_pick else pool
    sample = pd.concat(list(strata.values()), ignore_index=True)
    pop_total = len(normal_stock)
    info = {}
    for status_val, picked in strata.items():
        pop_n = int((normal_stock["status"] == status_val).sum())
        info[status_val] = {
            "population_n": pop_n,
            "population_pct": round(100.0 * pop_n / pop_total, 2) if pop_total else None,
            "sample_n": len(picked),
            "sample_pct": round(100.0 * len(picked) / len(sample), 2) if len(sample) else None,
            "population_weight": round((pop_n / pop_total) / (len(picked) / len(sample)), 4)
                                 if pop_total and len(sample) and len(picked) else None,
        }
    return sample, info


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    uni = universe()
    # 只留 4 位純數字代號（普通股票）：上一輪 bug 是依字母排序取前 N 檔，
    # 系統性抽到 00400A～00405A 這類 ETF 連結型代號（無真實 EPS/股價資料）。
    # universe() 本身的 is_warrant 過濾只擋 6 位純數字權證，不擋這種帶字母
    # 尾碼的 ETF 代號，所以這裡另外用「4位純數字」白名單過濾，不動共用的
    # universe.py（避免影響其他呼叫者）。
    normal_stock = uni[uni["stock_id"].str.match(r"^\d{4}$")].reset_index(drop=True)
    n_excluded = len(uni) - len(normal_stock)
    sample, strata_info = stratified_sample(normal_stock, SAMPLE_PER_STRATUM, SAMPLE_SEED)
    print(f"[multibagger] 分層抽樣驗證輪：{len(sample)} 檔（宇宙總數 {len(uni)} 檔，"
          f"過濾非4位數字普通股代號 {n_excluded} 檔，每層上限{SAMPLE_PER_STRATUM}檔，"
          f"隨機種子={SAMPLE_SEED}）")
    print(f"[multibagger] 分層資訊（母體比例 vs 樣本比例，之後算母體層級統計量"
          f"要用population_weight加權還原）：{json.dumps(strata_info, ensure_ascii=False)}")

    results = []
    errors = []
    for i, row in sample.iterrows():
        r = process_stock(row["stock_id"], row["status"], row.get("delist_date"))
        if "skip_reason" in r:
            errors.append(r)
        else:
            results.append(r)
        if (i + 1) % 50 == 0:
            print(f"  progress {i+1}/{len(sample)}  ok={len(results)}  skip={len(errors)}")

    all_moonshot = [row for r in results for row in r["moonshot_rows"]]
    moonshot_df = pd.DataFrame(all_moonshot)

    # 第1題：逐年基準機率（分母含下市股——用「該年有月頻資料」的樣本數股票，
    # 不是只算活到今天的），這裡小樣本輪先用「有 n_months>0 的股票」逐年判定
    # 是否於該年出現過起飛窗結束月。
    yearly_base_rate = {}
    if not moonshot_df.empty:
        moonshot_df["year"] = pd.to_datetime(moonshot_df["month_end"]).dt.year
        has_data_stocks = {r["stock_id"] for r in results}
        for y in sorted(moonshot_df["year"].unique()):
            hit = moonshot_df.loc[moonshot_df["year"] == y, "stock_id"].nunique()
            yearly_base_rate[int(y)] = {"n_moonshot_stocks": int(hit), "n_sample_universe": len(has_data_stocks)}

    status_breakdown = _survivorship_skip_breakdown(sample, results, errors)
    skip_category_summary = _skip_reason_category_summary(errors)

    moonshot_df.to_csv(OUT_DIR / "moonshot_windows_sample.csv", index=False)
    with open(OUT_DIR / "run_summary.json", "w", encoding="utf-8") as f:
        json.dump({
            "sample_size": len(sample), "n_ok": len(results), "n_skipped": len(errors),
            "sampling_method": "stratified（active/delisted各抽樣，見strata_info），"
                                "2026-09-18之前是單純隨機抽樣，兩者不可直接比較成功率",
            "strata_info": strata_info,
            "n_moonshot_windows_total": len(all_moonshot),
            "n_moonshot_stocks_total": moonshot_df["stock_id"].nunique() if not moonshot_df.empty else 0,
            "yearly_base_rate": yearly_base_rate,
            "yearly_base_rate_caveat": "分層抽樣後delisted被人為過抽，這個表**未依population_weight"
                                        "加權還原**，不能直接當母體逐年基準機率使用——只是描述性中間"
                                        "產出，見strata_info的population_weight欄位。",
            "status_breakdown": status_breakdown,
            "skip_reason_category_summary": skip_category_summary,
            "skip_reasons_full": [{"stock_id": e["stock_id"], "status": e["status"],
                                    "skip_reason": e["skip_reason"]} for e in errors],
        }, f, ensure_ascii=False, indent=2)

    print(f"[multibagger] 完成：ok={len(results)} skip={len(errors)} moonshot窗口={len(all_moonshot)}")
    print(f"[multibagger] 逐年基準機率（小樣本）：{json.dumps(yearly_base_rate, ensure_ascii=False)}")
    print(f"[multibagger] 存活者偏誤skip率分解：{json.dumps(status_breakdown, ensure_ascii=False)}")
    print(f"[multibagger] skip原因四類分佈（全體{len(errors)}筆）："
          f"{json.dumps(skip_category_summary, ensure_ascii=False)}")
    test = status_breakdown.get("_active_vs_delisted_test", {})
    if test.get("delisted_skip_rate_significantly_higher"):
        a, d = status_breakdown["active"], status_breakdown["delisted"]
        print(f"[multibagger] ⚠️⚠️⚠️ 本研究的存活者偏誤僅部分緩解：delisted股skip率"
              f"{d['skip_rate_pct']}% 顯著高於active股{a['skip_rate_pct']}%"
              f"（two-proportion z-test p={test['p_value']:.4g}），下市股實際納入率僅"
              f"{100 - d['skip_rate_pct']:.1f}%。不得只說「宇宙含下市股」就當作已解決。")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
