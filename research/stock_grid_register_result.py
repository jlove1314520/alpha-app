# -*- coding: utf-8 -*-
"""先.一三三-2c-判：#468～#474 個股網格單發結果登記（DevQueue 20261023-233101，驗證帽；只執行一次）。
寫法照 research/var1018_v1_register_result.py：主結果列引用「事前登記 #468」；
#469～#474（第 11 關參數懲罰佔位，自由參數 7 個 N 計 +7）各寫一列同步結果列、各自引用自己的事前登記編號，
selection_bias_ledger 的「事前登記與結果算 1 筆」合併後 N 仍是 +7，不多也不少。
用法（repo 根目錄）：python research/stock_grid_register_result.py [--dry-run] ；之後 python research/selection_bias_ledger.py"""
import json, sys
sys.path.insert(0, "research")
from trial_registry import register_trial

DRY = "--dry-run" in sys.argv
d = json.load(open("research/data/stock_grid_oneshot_result.json", encoding="utf-8"))
lim = json.load(open("research/data/stock_grid_oneshot_limit7_diag.json", encoding="utf-8"))
P, N = d["results"]["pessimistic"], d["results"]["neutral"]
assert d["trial_ids"] == [468, 469, 470, 471, 472, 473, 474]
assert P["verdict_mechanical"] == "FAIL" and N["verdict_mechanical"] == "FAIL" and d["verdict_overall"] == "FAIL"
assert d["holdout_touched"] is False and d["price_read_until"] == "2009-12-31"
st = P["daily_stats_1x"]
CAP = d["capital"]


def s(r):
    b, rc, y = r["benchmark_0050"], r["random_timing_control"], r["yearly_excess_vs_0050"]
    return (f"交易 {r['n_round_trips']} 筆；扣 1× 總報酬 {r['total_return_1x']:+.2%}、年化 {r['cagr_1x']:+.2%}"
            f"（0050 含息年化 {b['cagr_total_return']:+.2%}）；2×／3× 期末權益 {r['final_equity_2x']/CAP:.3f}／{r['final_equity_3x']/CAP:.3f} 億（<1 億＝淨虧）；"
            f"MDD 全期 {r['mdd_full_1x']:.1%}、2008-05～11 段 {r['mdd_2008_05_11_1x']:.1%}（0050 {b['mdd_full']:.1%}／{b['mdd_2008_05_11']:.1%}）；"
            f"隨機進出場時點控制組 {rc['n_random']} 次百分位 {rc['percentile']:.0f}（P95 {rc['random_p95']/CAP:.3f} 億、最大 {rc['random_max']/CAP:.3f} 億、kept_original {rc['kept_original_max']}）；"
            f"逐年超額 2007Q4 {y['2007Q4']['excess']:+.1%}、2008 {y['2008']['excess']:+.1%}、2009 {y['2009']['excess']:+.1%}（網格 {y['2009']['grid']:+.1%} vs 0050 {y['2009']['0050']:+.1%}）")


same = s(P) == s(N)
result = f"悲觀：{s(P)}。中性：{'同悲觀（數字完全相同）' if same else s(N)}。策略 1× 日頻 Sharpe {st['sharpe_daily']:.4f}、n={st['n_obs']}"
notes = ("機械判定兩假設皆 FAIL：判準 1 交易數 ≥100 過；判準 2 天條一過（MDD 約 −19.8%）；判準 3 第 8 關簡化版不過——"
         "扣 1× 年化 −3.47% 雖高於 0050 含息 −4.05%，但 1× 本身淨虧、2×／3× 淨利 <0；判準 4 隨機進出場控制組過"
         "（程式內 Bonferroni 用 TRIALS_REGISTRY.jsonl 列數 289 當 N 是錯的來源，帳本總 N 453 下門檻約 99.989 百分位，百分位 100 仍過；照實揭露、不改判）。"
         "failed_gates 對應：gate1＝淨利>0 不成立、gate4＝成本 2×／3× 不存活（第 8 關簡化版不在值域，寫在這裡）。"
         "死因（流程對、此假設無 edge）：2009 強多頭網格太早賣光（網格 +12.5% vs 0050 +75.0%），正是 PREREG 第 3 節事前寫的死法。"
         f"下市股缺資料 {d['n_missing_data_delisted']} 檔，網格從未在下市日持有，悲觀＝中性。"
         f"⚠️ 揭露：costs.limit_status() 寫死 ±10%，2015-06 前台股實為 ±7%（單發 0 次順延）；診斷 {lim['script']} 找到 "
         f"{lim['sells_executed_on_7pct_limitdown_lock_day']} 筆賣、{lim['buys_executed_on_7pct_limitup_lock_day']} 筆買落在 ±7% 一字鎖死日，"
         "偏誤方向使權益偏樂觀、修正只會更差、不翻轉 FAIL（修法提案 先.一三三-2c-限，互動視窗）。"
         "結果檔 research/data/stock_grid_oneshot_result.json、research/data/stock_grid_oneshot_limit7_diag.json；"
         "兩假設同屬一次試驗；事前登記 #468 起 N +7（第 11 關，自由參數 7 個）。")
CODE = ["research/stock_grid_oneshot.py", "research/stock_grid_limit7_diag.py",
        "docs/PREREG_STOCK_GRID_2007_2009_FINAL.md", "research/stock_grid_register_result.py"]
ROUND = "DevQueue 20261023-223103 單發、20261023-233101 驗證帽登記（先.一三三-2c-判）"

tid, row = register_trial(
    track="TW", name="stock_grid_tw2007q4_2009_oneshot",
    design="#468 單發（父筆 #468）：PREREG FINAL＋修訂 R1，前 60 日均成交金額前 50 名在市上市＋上櫃普通股（含之後下市），"
           "60 日均線中心、1×ATR20 格距、上下各 5 格，跌破 L-5 出清冷卻 20 日；驗證段 2007-10-01～2009-12-31，悲觀／中性兩假設，只跑一次、不碰 holdout",
    result=result, verdict="FAIL", notes=notes, round_note=ROUND,
    sharpe=st["sharpe_daily"], n_obs=st["n_obs"], skew=st["skew"], kurtosis=st["kurtosis"], periods_per_year=252,
    failed_gates=["gate1", "gate4"], code_paths=CODE, dry_run=DRY,
)
print("主結果列", tid)
for k, pid in enumerate(range(469, 475), start=2):
    t2, _ = register_trial(
        track="TW", name=f"stock_grid_tw2007q4_2009_oneshot_param_penalty_{k}",
        design=f"第 11 關參數懲罰佔位結果同步（非獨立試驗，父筆 #{pid}）：第 {k}／7 列；內容同主結果列 stock_grid_tw2007q4_2009_oneshot（#{tid}）。",
        result=f"同主結果列 #{tid}：兩假設皆 FAIL（1× 淨虧、2×／3× 淨利 <0）。",
        verdict="FAIL",
        notes=f"事前登記 #{pid}；第 11 關自由參數 7 個 N 計 +7 的第 {k} 列，判定與主結果列 #{tid} 同步，詳見該列。",
        round_note=ROUND,
        no_stats_reason=f"參數懲罰佔位列，統計量只記在主結果列 #{tid}，避免同一條日報酬序列重複進 V",
        failed_gates=["gate1", "gate4"], code_paths=CODE, dry_run=DRY,
    )
    print("佔位結果列", t2, "← 事前登記", pid)
