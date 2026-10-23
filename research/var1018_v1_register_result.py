# -*- coding: utf-8 -*-
"""先.一三三-1：#462 單發結果登記（DevQueue 20261023-180102 寫好；程式與結果檔 commit 後才執行，只執行一次）。
用法（repo 根目錄）：python research/var1018_v1_register_result.py ；之後 python research/selection_bias_ledger.py"""
import json, sys
sys.path.insert(0, "research")
from trial_registry import register_trial
d = json.load(open("research/data/var1018_v1_oneshot_result.json", encoding="utf-8"))
P, N = d["results"]["pessimistic"], d["results"]["neutral"]
st = P["daily_stats_strategy_1x"]
def s(r):
    c, dd = r["cost_1x"], r["drawdowns_1x"]
    return (f"策略 CAGR {c['strategy_cagr']:.2%}／基準 {c['benchmark_cagr']:.2%}／溢酬 {c['premium_cagr']:+.2%}；"
            f"MDD 策略 {dd['strategy_full']:.1%}（海嘯段 {dd['strategy_2007-10-30～2008-11-21']:.1%}、歐債段 {dd['strategy_2011-05-02～2011-12-19']:.1%}）"
            f"／基準 {dd['benchmark_full']:.1%}；隨機一半 {r['random_half_control']['frac_premium_positive']:.0%} 為正；8 期正 {r['n_periods_positive']}/8")
tid, row = register_trial(
    track="TW", name="var1018_v1_equal_weight_rebalance_tw2007h2_oneshot",
    design="#462 單發（父筆 #462）：PREREG FINAL 定稿條文＋R2（官方日檔有列價格、母體 1,126）＋R3（股利 FinMind＋官方補充）；"
           "t0 2007-07-02 等權、每 21 交易日再平衡 vs 同組不再平衡，2007-07-02～2014-12-31，悲觀／中性兩假設，只跑一次、不碰 holdout",
    result=f"悲觀：{s(P)}。中性：{s(N)}。0050 含息 CAGR {d['benchmark_0050']['cagr_total_return']:.2%}／MDD {d['benchmark_0050']['mdd']:.1%}",
    verdict="VIOLATES_SURVIVAL",
    notes=("兩假設都 VIOLATES_SURVIVAL（天條一：策略全期 MDD 約 −64%、2007-10～2008-11 段約 −58% >50%），不進後續判定；"
           "參考（不作判定）：溢酬 >0、隨機控制 100/100、3× 成本仍正、贏 0050，但逐期一致只有 4/8（門檻 7/8，同原試驗 #29 死因）；"
           f"母體 {d['n_universe']}、下市 {d['n_delisted_in_universe']}、缺資料下市 {d['n_missing_data_delisted']}；"
           f"官方除權息補充 {d['r3_official_exright_supplement']['n_in_universe_window']} 筆（近似 {d['r3_official_exright_supplement']['n_approx']}）；"
           f"設 0 停牌 {d['disclosures']['assumed_zero_return']['n']}、>±20% 跳動 {d['disclosures']['jumps_over_20pct']['n']}、未還原疑似 {d['disclosures']['unresolved_suspects_not_adjusted']['n']}、無法解析 {d['disclosures']['impossible']['n']}；"
           "結果檔 research/data/var1018_v1_oneshot_result.json；兩假設同屬一次試驗、N 只 +1（事前登記 #462）"),
    round_note="DevQueue 20261023-180102 單發（先.一三三-1）",
    sharpe=st["sharpe_daily"], n_obs=st["n_obs"], skew=st["skew"], kurtosis=st["kurtosis"], periods_per_year=252,
    failed_gates=["天條一 VIOLATES_SURVIVAL"],
    code_paths=["research/var1018_v1_oneshot.py", "docs/PREREG_VAR1018_V1_equal_weight_rebalance_tw2007_FINAL.md"],
)
print("已登記", tid)
