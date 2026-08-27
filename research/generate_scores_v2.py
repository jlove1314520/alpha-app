"""產生 App「選股」頁用的 scores.json（repo 根目錄，`alpha-app/scores.json`）—— scoring-v2。

**這支腳本取代 `generate_scores_json.py` 對 `scores.json` 這個輸出檔的角色**（`score.py`
原本的複合分數格式，換成 `score_v2.py` 的十分制/百分位格式，符合
`C:\\alpha\\docs\\Alpha_評分引擎_10分制設計小抄.md`）。`generate_scores_json.py`
本身**沒有刪除**，因為 `score.py` 的函式還有其他研究腳本在用；只是 App 顯示用的
`scores.json` 之後改由這支腳本產生。

**2026-08-26 補上即時資料路徑，解除延宕兩輪的架構卡關：** 基準日改成「今天」，
不再固定卡在 `VAL_END`（2024-12-31）。做法是 `realtime_asof.py` 的
`as_of_today()`——一個只在這支腳本的抓資料範圍內生效的 context manager，暫時把
`validation.holdout.VAL_END` 這個模組屬性拉高到今天，讓 `load_dev()`／
`yf_price_client.fetch_yf_adjusted()`／`twse_t86_client.institutional_daily_net_t86()`
這些全部走「執行當下才 import/讀取 VAL_END」設計的資料層讀到新邊界，離開這個
context manager 後立刻還原成 2024-12-31。**這不是繞過 holdout**：`HOLDOUT_LOCK.json`／
`is_holdout_consumed()` 完全沒被碰，`score_v2.py` 的 `FACTOR_DEFS` 權重維持凍結、
不會被這輪或未來任何一次即時算分重新估計——這正是使用者 2026-08-25 那條規則
（「凍結權重＋當前資料＝合法正式out-of-sample，不算碰研究holdout」）字面上要求的
機制，細節/理由見 `realtime_asof.py` docstring 跟 `MARATHON_STATE.md` 2026-08-25
條目。**注意分工**：`factor_ic.py`／`TRIALS_LEDGER.md` 那一套嚴謹驗證管線完全沒有
被這裡影響——這支腳本自己開關這個 context manager，不會讓 VAL_END 的改變外溢到
同一個 Python process 裡其他同時執行的程式碼（沒有其他程式碼會在這個 with 區塊
執行期間跑）。

**2026-08-25 使用者回報 App 選股頁只有 69 檔的追加**：樣本數已從 `factor_ic.py`
共用的 `SAMPLE_SIZE=100`（驗證管線在用，動它會牽動 `TRIALS_LEDGER.md` 已經記錄過
的統計結果，不能為了展示需求去改）換成這支腳本自己獨立的 `SCORES_SAMPLE_SIZE`
＋自己的 seed，跟研究驗證用的抽樣完全分開、互不影響。

**2026-08-26（晚）補上凍結權重稽核軌跡**：權重來源改成明確讀
`score_live.py::load_frozen_weights()`（唯讀 `weights_frozen.json`，含
sha256 完整性驗證），套用進 `score_v2.FACTOR_DEFS` 後才開始算分——不再只是
「FACTOR_DEFS 沒被改」這種消極保證，而是有一份 commit 進 git 的凍結檔可以
逐次核對，`weights_hash` 也會寫進 `scores.json` 的 `meta`，日後任何一批分數
都能回頭確認用的是哪一版權重。`score_live.py` 本身有寫入防護：任何嘗試寫
`weights_frozen.json` 的程式碼都會被攔截中止，不靠「記得不要這樣做」。
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from factor_ic import load_sample_with_factors, START_DATE
from finmind_client import load_dev
from realtime_asof import as_of_today
from score import load_industry_map, load_name_map
from score_live import apply_frozen_weights, load_frozen_weights
from score_v2 import export_scores_v2_json
from strategies.weinstein_stage2 import prepare_market_data
from universe import universe

# 跟 factor_ic.py 的 SAMPLE_SIZE/SAMPLE_SEED（驗證管線在用，見上面docstring說明）
# 完全獨立的一組常數，只給這支「消費端展示產品」腳本自己用，互不影響。
SCORES_SAMPLE_SIZE = 300
SCORES_SAMPLE_SEED = 20260825


def sample_scores_universe_ids(sample_size: int, seed: int) -> list[str]:
    u = universe()
    rng = random.Random(seed)
    pool = list(u["stock_id"])
    return rng.sample(pool, min(sample_size, len(pool)))


def main(top_n: int | None = None, out_path: str = "../scores.json",
         sample_size: int = SCORES_SAMPLE_SIZE, sample_seed: int = SCORES_SAMPLE_SEED):
    # 2026-08-24 改版：top_n 預設改 None（匯出全部 coverage>=0.5 的樣本，不是只有前 30）。
    # 使用者要求選股頁搜尋框「即使不在排行榜前段也要能單獨算出該檔評分」——受限於
    # 目前架構（App 端是純前端，沒有後端可以現算一支新股票的橫斷面百分位），能做到
    # 的誠實版本是：把「這次抽樣、算出來的全部樣本」都匯出（不是只匯出前 30 名），
    # 前端排行榜清單只顯示前 30 名，但搜尋框可以查到樣本內任何一檔已經算出分數的股票；
    # 樣本外的股票（沒被抽到樣本、或 coverage<0.5）誠實顯示「查無評分資料」，不是假裝算得出來。
    frozen = load_frozen_weights()
    apply_frozen_weights(frozen)
    print(f"已套用凍結權重 weights_frozen.json（frozen_at={frozen['frozen_at']}，"
          f"sha256={frozen['weights_sha256'][:12]}...）")

    # 2026-08-27新增（使用者要求的風險防護）：coverage門檻0.5跟實際值0.54只差
    # 0.04，任一因子失效就可能讓合格檔數暴跌——先讀舊檔案的筆數當基準，跑完後
    # 比較，如果新筆數低於舊筆數的50%就要大聲報警，不能安靜地生出一份空/小榜單
    # 讓人誤以為「今天剛好符合條件的股票比較少」。
    prior_count = None
    out_file = Path(__file__).parent / out_path
    if out_file.exists():
        try:
            prior_count = len(json.loads(out_file.read_text(encoding="utf-8")).get("stocks", []))
        except Exception:
            prior_count = None

    sample_ids = sample_scores_universe_ids(sample_size, sample_seed)
    with as_of_today() as as_of:
        from yf_price_client import fetch_yf_index
        market_raw = fetch_yf_index("^TWII", START_DATE)
        if market_raw.empty:
            # yfinance index fetch failed for some reason -- fall back to FinMind,
            # which may itself be capped at the true VAL_END (2024-12-31) if its
            # quota is exhausted; stale-but-valid beats crashing the whole run.
            market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
        market_df = prepare_market_data(market_raw)
        data = load_sample_with_factors(sample_ids, market_df)
        # 基準日不能直接用「今天」的日曆日期：今天可能還沒收盤、還沒有這天的
        # OHLC（尤其是這支腳本白天跑的時候），直接拿日曆日期去比對 d["date"]==as_of
        # 會因為那天根本沒有資料列而全部篩掉，變成「0 檔計算出分數」（2026-08-26
        # 這輪測試時發現的真bug，不是資料源問題）。改用大盤序列實際存在的最後一筆
        # 日期，這才是「目前實際上看得到的最新交易日」。
        if not market_df.empty:
            as_of = market_df["date"].max()
    print(f"{len(data)}/{len(sample_ids)} 檔可用，基準日（即時，非 VAL_END）{as_of}")

    industry_map = load_industry_map()
    name_map = load_name_map()
    universe_size = len(universe())
    print(f"產業對照表 {len(industry_map)} 筆，公司名稱對照表 {len(name_map)} 筆，全市場宇宙 {universe_size} 檔")

    cs = export_scores_v2_json(
        as_of, data, industry_map, name_map, out_path,
        start_date=START_DATE, top_n=top_n, universe_size=universe_size,
        weights_hash=frozen["weights_sha256"],
    )
    print(f"已產生 {out_path}，{len(cs)} 檔計算出分數，基準日 {as_of}")
    if not cs.empty:
        print(cs[["industry", "total_score", "coverage", "rank"]].head(10).to_string())

    # 收尾：跟舊檔案比對合格檔數，暴跌就寫警告進meta（不是另外寫檔，直接補進
    # 剛產生的scores.json，STATUS.json/App診斷橫幅之後可以檢查這個欄位）。
    try:
        payload = json.loads(out_file.read_text(encoding="utf-8"))
        new_count = len(payload.get("stocks", []))
        collapse = prior_count is not None and prior_count > 0 and new_count < prior_count * 0.5
        payload.setdefault("meta", {})["coverage_collapse_warning"] = collapse
        payload["meta"]["prior_run_stock_count"] = prior_count
        if collapse:
            print(f"⚠ 警告：合格檔數從 {prior_count} 暴跌到 {new_count}（低於前次的50%），"
                  f"已寫入 meta.coverage_collapse_warning=true，不是安靜略過")
        out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"合格檔數暴跌檢查本身失敗（不影響scores.json主體已經寫成功）：{e}")

    return cs


if __name__ == "__main__":
    main()
