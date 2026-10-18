"""先.一一三-B1：V2／V4／V5 的事前登記列與結果列（用 trial_registry.register_trial，綁程式 commit）。

用法：
  python research/var1018_register.py prereg            # 三條事前登記（verdict＝未結案）
  python research/var1018_register.py result V2 <事前登記編號>   # 跑完後登記結果列（讀 research/data/var1018_v2_result.json）
事前登記列與結果列依先.一〇三-15 規則合併成一筆試驗（N 各 +1）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

from trial_registry import register_trial

R = Path(__file__).parent
SPECS = {
    "V2": dict(track="US", name="var1018_v2_turn_of_month_spx_taiex1990_prereg", script="research/var1018_v2_turn_of_month.py",
               doc="docs/PREREG_DRAFT_VAR1018_V2_turn_of_month_spx_taiex1990.md",
               design="墓園變形方向 V2（#25 月轉效應換市場）：S&P 500 1990～2024＋TAIEX 1990～2009 單發；窗口＝月底＋次月前 3 個交易日；洗牌 N＝200；兩市場都要 diff>0、百分位≥90、對半切兩半>0；天條一用窗口策略回撤"),
    "V4": dict(track="TW", name="var1018_v4_short_margin_reversed_tw2007_prereg", script="research/var1018_v4_short_margin_reversed.py",
               doc="docs/PREREG_DRAFT_VAR1018_V4_short_margin_ratio_tw2007_reversed.md",
               design="墓園變形方向 V4（#68 券資比反向）：台股 2007～2014 單發；因子＝−券資比、20 日不重疊快照 IC；每期打散 N＝500；平均 IC>0、百分位≥90、兩半>0；天條一用前 20% 等權回撤"),
    "V5": dict(track="TW", name="var1018_v5_january_reversal_tw_prereg", script="research/var1018_v5_january_reversal.py",
               doc="docs/PREREG_DRAFT_VAR1018_V5_january_reversal_tw.md",
               design="墓園變形方向 V5（#66 稅損 1 月反轉換市場）：台股全市場 2011～2024 的 14 個 1 月單發；1～10 月最差 20% 隔年 1 月，扣成本 1×、漲跌停無法成交、20 日均成交值≥3,000 萬；隨機抽同數量 N＝500；超額>0、百分位≥90、兩半>0；天條一用 1 月策略回撤"),
}


def main(argv: list[str]) -> int:
    if argv[:1] == ["prereg"]:
        for k, s in SPECS.items():
            tid, row = register_trial(
                track=s["track"], name=s["name"], design=s["design"],
                result="未跑（事前登記：參數一次定死、只跑一次）", verdict="未結案",
                notes=f"先.一一三-B1（2026-10-18 總司令裁示放行）；PREREG {s['doc']}；程式 {s['script']}；計入 N＋1（與結果列合併）",
                no_stats_reason="事前登記列，尚未執行", round_note="互動視窗單發（先.一一三-B1），不屬任何馬拉松輪次",
                code_paths=[s["script"], "research/var1018_twdata.py", s["doc"]] if k != "V2" else [s["script"], s["doc"]],
            )
            print(k, "事前登記 #", tid)
        return 0
    if argv[:1] == ["result"] and len(argv) == 3:
        k, pre = argv[1], int(argv[2])
        s = SPECS[k]
        res = json.loads((R / "data" / f"var1018_{k.lower()}_result.json").read_text(encoding="utf-8"))
        v = res["verdict"]
        if k == "V2":
            summ = "；".join(f"{m} diff={r['diff']:+.5f} 洗牌百分位 {r['null_percentile']:.1f} 兩半 {[round(h, 5) for h in r['half_diffs']]}"
                            for m, r in res["results"].items())
        elif k == "V4":
            summ = (f"{res['n_periods']} 期、平均 IC {res['mean_ic']:+.4f}、null 百分位 {res['null_percentile']:.1f}、兩半 "
                    f"{res['half_mean_ic']}；前 20% 終值 {res['top20_final_equity']}；天條一 {res['survival_segments']}")
        else:
            summ = (f"{res['n_januaries']} 個 1 月、平均超額（淨 1×）{res['mean_excess_net_1x']:+.4f}、null 百分位 {res['null_percentile']:.1f}、兩半 "
                    f"{res['half_mean_excess']}；1 月策略 MDD {res['january_only_strategy_mdd_pct_1x']}%")
        tid, row = register_trial(
            track=s["track"], name=s["name"].replace("_prereg", ""), design=s["design"], result=summ, verdict=v,
            notes=f"事前登記 #{pre}；先.一一三-B1 單發結果；結果檔 research/data/var1018_{k.lower()}_result.json；PREREG {s['doc']}",
            no_stats_reason="單發檢定（日曆效應／IC／事件），不是可部署策略的 Sharpe 報告", round_note="互動視窗單發（先.一一三-B1），不屬任何馬拉松輪次",
            failed_gates=None if v == "PASS" else [v],
            code_paths=[s["script"]],
        )
        print(k, "結果列 #", tid, v)
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
