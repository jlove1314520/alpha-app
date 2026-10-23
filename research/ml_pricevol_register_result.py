# -*- coding: utf-8 -*-
"""先.一三三-2d-判：#475 ML 價量單發結果登記（DevQueue 20261023-233101，驗證帽；只執行一次）。
寫法照 research/var1018_v1_register_result.py：結果列引用「事前登記 #475」，selection_bias_ledger 合併後 N 不變。
用法（repo 根目錄）：python research/ml_pricevol_register_result.py [--dry-run] ；之後 python research/selection_bias_ledger.py"""
import json, sys
sys.path.insert(0, "research")
from trial_registry import register_trial

DRY = "--dry-run" in sys.argv
d = json.load(open("research/data/ml_pricevol_oneshot_result.json", encoding="utf-8"))
P, N = d["results"]["pessimistic"], d["results"]["neutral"]
assert d["trial_id"] == 475 and d["holdout_touched"] is False
assert P["verdict_mechanical"] == N["verdict_mechanical"] == d["verdict_overall"] == "VIOLATES_SURVIVAL"
b = d["benchmark_0050"]


def s(r):
    y, bi, rc = r["yearly_excess_vs_0050"], r["bimonthly"], r["random_label_control"]
    return (f"交易 {r['n_trades_1x']} 筆；含現金總淨值 MDD 全期 {r['mdd_full_1x']:.2%}、2008-05～11 段 {r['mdd_2008_05_11_1x']:.2%}"
            f"（0050 {b['mdd_full']:.1%}）；參考（天條一已否決、不作判定）：扣 1× 年化 {r['cagr_1x']:+.2%}（0050 含息 {b['cagr_total_return']:+.2%}，超額 {r['excess_cagr_1x']:+.2%}）、"
            f"2×／3× 期末 {r['final_2x']:.3f}／{r['final_3x']:.3f}（<1）；隨機標籤 {rc['n_random']} 次百分位 {rc['percentile']:.0f}（P95 {rc['p95']:.3f}、最大 {rc['max']:.3f}）；"
            f"雙月頻超額 {bi['excess_cagr_1x']:+.2%}（MDD {bi['mdd_full_1x']:.1%}）；逐年超額 "
            + "、".join(f"{k} {v:+.1%}" for k, v in y.items()))


tr = d["training_unverifiable_share_by_fold"]
tid, row = register_trial(
    track="TW", name="ml_pricevol_tw2008_2012_oneshot",
    design="#475 單發（父筆 #475）：PREREG FINAL＋修訂 R1（採甲）＋R2（固定 70／30）；HistGradientBoostingRegressor 預設參數、10 個既有價量因子，"
           "每年 1 月擴張視窗重訓，測試年 2008～2012 月頻，前 30 名等權占淨值 70%、跌出前 90 名才賣；悲觀／中性兩假設，只跑一次、2013 只讀第一個交易日開盤、不碰 holdout",
    result=f"悲觀：{s(P)}。中性：同悲觀（隨機標籤最大值 {N['random_label_control']['max']:.3f} 不同，其餘數字完全相同）。",
    verdict="VIOLATES_SURVIVAL",
    notes=("兩假設都 VIOLATES_SURVIVAL（天條一：含現金總淨值全期 MDD −52.75% >50%，落在 2008-05～11 空頭段），依 PREREG 不進後續判定；"
           "參考：第 8 關簡化版也不過（2×／3× 淨虧）、隨機標籤 100 次的百分位解析度達不到 Bonferroni N=453 門檻 99.989、照列不作判定。"
           "死因（流程對、此假設無 edge 足以抵銷曝險）：70／30 仍擋不住 2008 選到的中小型股崩跌（2008 策略 −45.2% vs 0050 −43.3%）。"
           "每折訓練樣本回看期落在官方不可佐證區比例："
           + "、".join(f"{k} {v['share']:.1%}" for k, v in tr.items()) + "。"
           f"下市股缺資料 {d['n_missing_data_delisted']} 檔、從未持有至下市日（悲觀＝中性）；adjust events 錯誤 {d['adjust_events']['n_codes_events_error']} 檔。"
           "⚠️ costs.limit_status() 寫死 ±10%，2015-06 前實為 ±7%（先.一三三-2c-限，互動視窗），照 PREREG 原樣使用。"
           "結果檔 research/data/ml_pricevol_oneshot_result.json；兩假設同屬一次試驗；事前登記 #475，N 不另計。"),
    round_note="DevQueue 20261023-230101 單發、20261023-233101 驗證帽登記（先.一三三-2d-判）",
    no_stats_reason="單發程式結果檔只存期末權益／年化／MDD，沒有輸出日報酬序列，算不出 Sharpe 四件組；不重跑單發補算（只跑一次原則）",
    failed_gates=["gate1"],  # 六關第 1 關（MDD 可接受）；天條一 VIOLATES_SURVIVAL 寫在 notes
    code_paths=["research/ml_pricevol_oneshot.py", "docs/PREREG_ML_PRICEVOL_2006_2012_FINAL.md", "research/ml_pricevol_register_result.py"],
    dry_run=DRY,
)
print("已登記", tid)
