import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import mem_guard; mem_guard.install()
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import pandas as pd
from factor_ic import sample_universe_ids, load_sample_with_factors, SAMPLE_SEED, SAMPLE_SIZE, START_DATE
from finmind_client import load_dev
import score as S
from strategies.weinstein_stage2 import prepare_market_data
from validation.holdout import VAL_END

AS_OF = "2024-12-30"
ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
market_df = prepare_market_data(load_dev("TaiwanStockPrice", "TAIEX", START_DATE))
data = load_sample_with_factors(ids, market_df)
imap, nmap = S.load_industry_map(), S.load_name_map()
print(len(data), "檔可用；as_of", AS_OF)

def top(cs, n=20):
    t = cs.head(n).copy()
    t["name"] = t["stock_id"].map(nmap)
    return t

# 舊榜（方案A）：三成分、門檻2、無普通股過濾
S.SCORE_COMPONENTS = ["eps_family", "revenue_surprise", "low_vol"]; S.MIN_COMPONENTS_FOR_RANKING = 2
old_all = S.compute_scores_at_date(AS_OF, data, imap)
old = S.eligible_for_ranking(old_all)
# 新榜（方案B）：只 low_vol、門檻1、普通股資格池
S.SCORE_COMPONENTS = ["low_vol"]; S.MIN_COMPONENTS_FOR_RANKING = 1
new_all = S.compute_scores_at_date(AS_OF, data, imap)
pool = S._common_stock_pool(new_all, nmap)
new = S.eligible_for_ranking(pool)
# 對照：方案B但沒有普通股過濾（顯示前置條件的必要性）
new_nofilter = S.eligible_for_ranking(new_all)

def dist(t): return t["industry"].value_counts().to_dict()
res = {
 "as_of": AS_OF, "n_loaded": len(data),
 "old_eligible": len(old), "new_scored_all": len(new_all), "new_pool_after_common_stock": len(pool), "new_eligible": len(new),
 "excluded_by_common_stock_filter": sorted(set(new_all["stock_id"]) - set(pool["stock_id"])),
 "old_top20": [(r.stock_id, r.name, r.industry) for r in top(old).itertuples()],
 "new_top20": [(r.stock_id, r.name, r.industry) for r in top(new).itertuples()],
 "nofilter_top20": [(r.stock_id, r.name, r.industry) for r in top(new_nofilter).itertuples()],
 "old_top20_industry": dist(old.head(20)), "new_top20_industry": dist(new.head(20)), "nofilter_top20_industry": dist(new_nofilter.head(20)),
 "overlap_old_new_top20": len(set(old.head(20).stock_id) & set(new.head(20).stock_id)),
}
# 端到端：export 到暫存路徑（不碰 repo 根目錄 scores.json）
import tempfile, os
out = os.path.join(tempfile.gettempdir(), "scores_B_test.json")  # 暫存，不碰 repo 根目錄 scores.json
S.export_scores_json(AS_OF, data, imap, out, top_n=30, name_map=nmap)
j = json.load(open(out, encoding="utf-8"))
res["export_meta_scheme"] = j["_meta"]["score_scheme"]; res["export_n"] = len(j["scores"])
res["export_row_keys"] = sorted(j["scores"][0].keys())
json.dump(res, open(Path(__file__).parent / "data" / "diag_score_scheme_B_compare.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(json.dumps({k: v for k, v in res.items() if k not in ("old_top20","new_top20","nofilter_top20")}, ensure_ascii=False, indent=1))
for k in ("old_top20","new_top20","nofilter_top20"):
    print(k); [print("  ", x) for x in res[k]]
