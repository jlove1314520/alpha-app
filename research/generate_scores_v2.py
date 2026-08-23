"""產生 App「選股」頁用的 scores.json（repo 根目錄，`alpha-app/scores.json`）—— scoring-v2。

**這支腳本取代 `generate_scores_json.py` 對 `scores.json` 這個輸出檔的角色**（`score.py`
原本的複合分數格式，換成 `score_v2.py` 的十分制/百分位格式，符合
`C:\\alpha\\docs\\Alpha_評分引擎_10分制設計小抄.md`）。`generate_scores_json.py`
本身**沒有刪除**，因為 `score.py` 的函式還有其他研究腳本在用；只是 App 顯示用的
`scores.json` 之後改由這支腳本產生。

基準日一樣沿用 `VAL_END`（`load_dev()` 架構上的截斷點），不是即時資料——這是既有、
已經在 `FACTORS.md`/`STRATEGY_LOG.md` 揭露過的架構限制，這輪沒有動它。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from factor_ic import sample_universe_ids, load_sample_with_factors, SAMPLE_SEED, SAMPLE_SIZE, START_DATE
from finmind_client import load_dev
from score import load_industry_map, load_name_map
from score_v2 import export_scores_v2_json
from strategies.weinstein_stage2 import prepare_market_data
from universe import universe
from validation.holdout import VAL_END


def main(top_n: int | None = None, out_path: str = "../scores.json"):
    # 2026-08-24 改版：top_n 預設改 None（匯出全部 coverage>=0.5 的樣本，不是只有前 30）。
    # 使用者要求選股頁搜尋框「即使不在排行榜前段也要能單獨算出該檔評分」——受限於
    # 目前架構（App 端是純前端，沒有後端可以現算一支新股票的橫斷面百分位），能做到
    # 的誠實版本是：把「這次抽樣、算出來的全部樣本」都匯出（不是只匯出前 30 名），
    # 前端排行榜清單只顯示前 30 名，但搜尋框可以查到樣本內任何一檔已經算出分數的股票；
    # 樣本外的股票（沒被抽到樣本、或 coverage<0.5）誠實顯示「查無評分資料」，不是假裝算得出來。
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    market_df = prepare_market_data(market_raw)
    data = load_sample_with_factors(sample_ids, market_df)
    print(f"{len(data)}/{len(sample_ids)} 檔可用")

    industry_map = load_industry_map()
    name_map = load_name_map()
    universe_size = len(universe())
    print(f"產業對照表 {len(industry_map)} 筆，公司名稱對照表 {len(name_map)} 筆，全市場宇宙 {universe_size} 檔")

    cs = export_scores_v2_json(
        VAL_END, data, industry_map, name_map, out_path,
        start_date=START_DATE, top_n=top_n, universe_size=universe_size,
    )
    print(f"已產生 {out_path}，{len(cs)} 檔計算出分數，基準日 {VAL_END}")
    if not cs.empty:
        print(cs[["industry", "total_score", "coverage", "rank"]].head(10).to_string())
    return cs


if __name__ == "__main__":
    main()
