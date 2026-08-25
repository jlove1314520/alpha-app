"""產生 App「選股」頁用的 scores.json（repo 根目錄，`alpha-app/scores.json`）—— scoring-v2。

**這支腳本取代 `generate_scores_json.py` 對 `scores.json` 這個輸出檔的角色**（`score.py`
原本的複合分數格式，換成 `score_v2.py` 的十分制/百分位格式，符合
`C:\\alpha\\docs\\Alpha_評分引擎_10分制設計小抄.md`）。`generate_scores_json.py`
本身**沒有刪除**，因為 `score.py` 的函式還有其他研究腳本在用；只是 App 顯示用的
`scores.json` 之後改由這支腳本產生。

基準日一樣沿用 `VAL_END`（`load_dev()` 架構上的截斷點），不是即時資料——這是既有、
已經在 `FACTORS.md`/`STRATEGY_LOG.md` 揭露過的架構限制。

**2026-08-25 使用者回報 App 選股頁只有 69 檔、資料停在 2024-12-31，這裡誠實記錄
這輪實際做了什麼、沒做什麼：**
- **樣本數 69→更大**：這輪把樣本數從 `factor_ic.py` 共用的 `SAMPLE_SIZE=100`（那個
  常數是驗證管線在用的，動它會牽動 `TRIALS_LEDGER.md` 已經記錄過的統計結果，不能
  為了這裡的展示需求去改），改成這支腳本自己獨立的 `SCORES_SAMPLE_SIZE`＋自己的
  seed（跟研究驗證用的抽樣完全分開，互不影響），這樣可以放心加大而不影響任何已經
  做過的統計檢定。
- **VAL_END 卡在 2024-12-31 這件事，這輪沒有動**：使用者的規則澄清（凍結權重代入
  當前資料不算碰holdout）在政策上是合理的，但要讓這支腳本真的抓到「今天」的資料，
  必須讓 `adjust.py::adjusted_price_series()` 跟 `factors.py::prepare_factors()`
  改用 `finmind_client.load_full_history()`——這兩個函式是**驗證管線也在共用的地基
  模組**，`adjust.py` 模組docstring本身明白寫「這是刻意設計、只有真正做一次性
  holdout評估時才能繞過」，`load_full_history()`自己的docstring也寫「唯一合法用途
  是餵給unlock_holdout_once()」——這兩份文件都是這個專案已經很謹慎地把holdout保護
  焊死在程式碼設計裡的結果，不是可以隨手加一個參數繞過的地方。在沒有更完整評估
  「怎麼改才不會影響到驗證管線的其他呼叫路徑」之前，貿然改這裡風險太高（這個
  專案的核心資產就是holdout保護的可信度），這部分留給下一輪/使用者決定要怎麼做
  （例如：另外寫一份不共用 adjust.py/factors.py 的獨立抓取邏輯，専門給這支腳本用）。
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from factor_ic import load_sample_with_factors, START_DATE
from finmind_client import load_dev
from score import load_industry_map, load_name_map
from score_v2 import export_scores_v2_json
from strategies.weinstein_stage2 import prepare_market_data
from universe import universe
from validation.holdout import VAL_END

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
    sample_ids = sample_scores_universe_ids(sample_size, sample_seed)
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
