"""產生 App「選股」頁用的 scores.json（repo 根目錄，`alpha-app/scores.json`）。

2026-08-24 補上：`export_scores_json()` 原本只寫 `stock_id`，App 選股頁只能
顯示代號，使用者要求改成「公司名（代號）」——這支腳本把 `load_name_map()`
（`TaiwanStockInfo` 的 `stock_name` 欄位）一併傳進去。

之前（Part 1）產生 scores.json 是用一次性的 inline `python -c` 指令，沒有
留下正式腳本；這次順便把它寫成一支有文件記錄、可重複執行的腳本，之後要
重新產生（例如補上新因子、換基準日）直接重跑這支即可，不用再現場拼指令。

基準日目前固定用 `VAL_END`（`load_dev()` 架構上的截斷點），不是即時資料——
這是已知、已在 `FACTORS.md`/`STRATEGY_LOG.md` 揭露過的架構限制，這裡沒有
偷偷繞過。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from factor_ic import sample_universe_ids, load_sample_with_factors, SAMPLE_SEED, SAMPLE_SIZE, START_DATE
from finmind_client import load_dev
from score import load_industry_map, load_name_map, export_scores_json
from strategies.weinstein_stage2 import prepare_market_data
from validation.holdout import VAL_END


def main(top_n: int = 30, out_path: str = "../scores.json"):
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    market_df = prepare_market_data(market_raw)
    data = load_sample_with_factors(sample_ids, market_df)
    print(f"{len(data)}/{len(sample_ids)} 檔可用")

    industry_map = load_industry_map()
    name_map = load_name_map()
    print(f"產業對照表 {len(industry_map)} 筆，公司名稱對照表 {len(name_map)} 筆")

    cs = export_scores_json(VAL_END, data, industry_map, out_path, top_n=top_n, name_map=name_map)
    print(f"已產生 {out_path}，{len(cs)} 檔，基準日 {VAL_END}")
    print(cs[["stock_id", "stock_name", "industry", "composite", "rank"]].head(10).to_string())
    return cs


if __name__ == "__main__":
    main()
