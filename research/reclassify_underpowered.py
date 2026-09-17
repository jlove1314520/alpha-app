# -*- coding: utf-8 -*-
"""47筆FAIL的「死於檢定力不足」重新分類（2026-09-18 總司令裁示【研究方向
重構】階段一.3）。

**問題**：對每一筆FAIL回答「它的效果量估計值，是不是落在該構造的最小
可偵測alpha/IC以下？」是→UNDERPOWERED（不是FAIL，是「沒測出來」，列入
候選重測清單）；否→維持FAIL。

**方法侷限，誠實先講在前面**：只有兩種家族的統計檢定有現成、封閉形式
的檢定力公式可以套：
1. Pearson/Spearman相關係數(IC)類：SE≈1/sqrt(n-3)（Fisher z近似），
   MDE_IC=(z_0.975+z_0.80)/sqrt(n-3)。
2. CAPM alpha迴歸類：`power_budget.py::min_detectable_alpha()`，
   輸入年化追蹤誤差與樣本年數。
`TRIALS_FAILED_GATES_BACKFILL.jsonl`裡47筆FAIL裡，只有10筆是乾淨的
IC+n格式（#187/#190/#203/#204/#205/#207/#208/#229/#233/#239），其餘
約30筆是「訊號 vs 模擬隨機控制組percentile」這種**經驗分布比對**，
沒有封閉形式的SE——要嚴謹算這類測試的檢定力，需要比照`#74`
`synthetic_power_curve_gate74.py`的做法（注入已知強度訊號、重複多次
量測通過率），是另一個獨立工作量，**本輪未做，誠實標記為
`not_assessed_needs_simulation`，不是判定它們不是underpowered**。

**判準（每一筆都要同時滿足，缺一不能標UNDERPOWERED）**：
1. 檢定的方向必須與事前綁定的方向一致（原文明寫「同號」「符合預測
   方向」「same_sign=True」才算，若原文明寫「方向相反」「符合預期
   相反」則排除——方向錯誤是證據，不是檢定力不足能解釋的）。
2. TRAIN/VAL兩期本身方向要一致（不能是「train正val負」這種期間內部
   矛盾，那種矛盾用「更多資料」不能簡單解釋成同一個真實效應）。
3. 用該期樣本數n算出的MDE_IC必須大於實際觀測到的|IC|（效果量落在
   偵測門檻以下）。

跑法：`python research/reclassify_underpowered.py`（純本機計算，
零外部請求，讀取本模組內建的10筆手動核對過的IC+n數字——不是重新解析
TRIALS_REGISTRY.jsonl自動抽取，因為欄位格式因試驗類型而異，自動抽取
容易抽錯，10筆全部人工核對過原始result欄位文字，見下方每筆的
`source_quote`）。輸出`research/UNDERPOWERED_RECLASSIFICATION.jsonl`
（append-only，比照`TRIALS_FAILED_GATES_BACKFILL.jsonl`同一個
「不改寫TRIALS_REGISTRY.jsonl本身、用amends_id指回原始編號」精神）。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scipy.stats import norm

TZ = timezone(timedelta(hours=8))
OUT = Path(__file__).parent / "UNDERPOWERED_RECLASSIFICATION.jsonl"

Z_SIG = norm.ppf(1 - 0.05 / 2)
Z_POWER_80 = norm.ppf(0.80)


def mde_ic(n: int) -> float:
    """Fisher z近似：SE(r)≈1/sqrt(n-3)，MDE=(z_sig+z_pow)*SE。"""
    if n <= 3:
        return float("nan")
    se = 1 / ((n - 3) ** 0.5)
    return round(float((Z_SIG + Z_POWER_80) * se), 4)


# 人工逐筆核對過的10筆IC+n乾淨案例（見TRIALS_REGISTRY.jsonl原始result欄位）。
# direction_ok: 該筆本身的result/notes是否明寫「同號」「符合預測方向」
# 「same_sign=True」（True）或明寫「方向相反」「與預期相反」（False）。
CANDIDATES = [
    dict(id=187, name="#51子事件2現金增資折價cheap gate",
         val_ic=-0.2289, val_n=40, direction_ok=True,
         source_quote="同號（皆負，符合預測方向）...但VAL Spearman p=0.1554未達0.10顯著水準"),
    dict(id=190, name="cb_conversion_price_reset_gate1",
         val_ic=0.0430, val_n=1047, direction_ok=False,
         source_quote="同號但方向與事前綁定的負相關預期相反"),
    dict(id=203, name="f_us_low_vol大型股tier N=90重跑",
         val_ic=0.0255, val_n=49, direction_ok=False,
         source_quote="train/val正負號相反"),
    dict(id=204, name="f_us_momentum_12m大型股tier N=90重跑",
         val_ic=-0.0186, val_n=49, direction_ok=None,
         source_quote="train/val同號（皆負）——動能理論預期為正，本輪原文未明講是否視為「方向相反」，保守排除"),
    dict(id=205, name="f_us_reversal_1m大型股tier N=90重跑",
         val_ic=0.0166, val_n=49, direction_ok=None,
         source_quote="train/val同號（皆正）——反轉因子正負號慣例依構造而定，本輪無法從原文確認是否符合事前方向，保守排除"),
    dict(id=207, name="f_us_momentum_12m中型股tier N=90重跑",
         val_ic=0.0143, val_n=49, direction_ok=None,
         source_quote="同204，保守排除"),
    dict(id=208, name="f_us_reversal_1m中型股tier N=90重跑",
         val_ic=0.0066, val_n=49, direction_ok=None,
         source_quote="同205，保守排除"),
    dict(id=229, name="#65產業龍頭股跨期領先-落後動能",
         val_ic=0.0094, val_n=193, direction_ok=True,
         source_quote="null_percentile=87.5(need>=90.0) same_sign=True"),
    dict(id=233, name="short_margin_ratio_gate68第1關cheap IC gate",
         val_ic=-0.0548, val_n=47, direction_ok=False,
         source_quote="事前綁定方向為正...實測train/val的IC皆為負...經濟方向與假設相反，判定方向假設證偽"),
    dict(id=239, name="option_oi_pcr_gate69第1關cheap gate",
         val_ic=0.0395, val_n=970, direction_ok=True,
         source_quote="train/val同號皆正(符合事前綁定方向)但VAL贏過洗牌null未過90.0門檻"),
]

NOT_ASSESSED_IDS = [189, 193, 194, 196, 197, 198, 199, 200, 201, 202, 209, 212, 213, 214,
                    215, 216, 217, 218, 219, 220, 222, 223, 224, 227, 228, 230, 232, 234,
                    235, 236, 237, 238, 241, 242, 243, 244]


def main() -> None:
    now = datetime.now(TZ).isoformat(timespec="seconds")
    records = []
    underpowered_count = 0
    for c in CANDIDATES:
        mde = mde_ic(c["val_n"])
        below_mde = bool(abs(c["val_ic"]) < mde)
        verdict = "UNDERPOWERED" if (c["direction_ok"] is True and below_mde) else "FAIL_CONFIRMED"
        if verdict == "UNDERPOWERED":
            underpowered_count += 1
        records.append({
            "amends_id": c["id"], "name": c["name"],
            "val_ic": c["val_ic"], "val_n": c["val_n"], "mde_ic_80pct_power": mde,
            "direction_ok": c["direction_ok"], "abs_ic_below_mde": below_mde,
            "reclassification": verdict, "source_quote": c["source_quote"],
            "method": "Fisher z近似 MDE_IC=(z0.975+z0.80)/sqrt(n-3)，"
                      "direction_ok!=True（含None＝無法從原文確認）一律不得標UNDERPOWERED",
            "reclassified_at": now,
        })
        print(f"#{c['id']:>4} {c['name'][:30]:30}  VAL IC={c['val_ic']:+.4f}  n={c['val_n']:>5}  "
              f"MDE={mde:.4f}  direction_ok={c['direction_ok']!s:>5}  → {verdict}")

    for tid in NOT_ASSESSED_IDS:
        records.append({
            "amends_id": tid, "reclassification": "not_assessed_needs_simulation",
            "method": "percentile-vs-模擬隨機控制組類測試沒有封閉形式SE，需要比照"
                      "#74 synthetic_power_curve_gate74.py的注入式檢定力量測方法，本輪未做",
            "reclassified_at": now,
        })

    OUT.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")
    print(f"\n47筆FAIL裡：{underpowered_count}筆重分類為UNDERPOWERED、"
          f"{len(CANDIDATES) - underpowered_count}筆維持FAIL（含方向錯誤/期間內部矛盾/"
          f"無法確認方向而保守排除）、{len(NOT_ASSESSED_IDS)}筆屬於沒有封閉形式power公式的"
          f"測試類型，標記not_assessed_needs_simulation（不是判定非underpowered）。")
    print(f"寫入 {OUT.name}")


if __name__ == "__main__":
    main()
