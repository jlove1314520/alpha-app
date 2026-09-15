# -*- coding: utf-8 -*-
"""打平0050所需毛alpha計算表（2026-09-15 總司令裁示【持有期與成本結構重新
檢視】一.1，戴驗證帽）。

**要回答的問題（總司令原話）**：「不同持有期下，我們需要多少毛alpha才能
打平0050」——這張表直接決定「該不該繼續做高周轉選股」。背景是兩個獨立
發現指向同一件事：#243 regime overlay的MDD改善扣完切換成本只剩1.8%、
我們vs0050三榜全輸且t5周轉一年約50次×0.585%≈29%成本——毛報酬還行，
成本吃光。

**核心邏輯（一句話）**：假設我方選股跟0050承擔同樣的市場曝險（貝他相同），
唯一的差異是我方頻繁進出、0050買進持有幾乎零周轉。那麼我方要net報酬
打平0050，每次換股至少要比0050多賺出「一次來回成本」，一年換手N次
就要多賺N次的份——**這正是「打平所需毛alpha」**。

**兩種年化算法，刻意都算、都印出來，不是只選一個**：
- `_simple`：總司令原話自己用的算法（次數×單次成本，線性近似，
  t5例子：50×0.585%≈29%）。
- `_geometric`：複利精確版——`((1-單次成本)**-年化次數 - 1)`。**這個數字
  一定比simple版更高**（複利對成本的侵蝕比線性加總更兇，要用複利報酬
  補回來也要更多），差距在t5這種高周轉窗口尤其明顯（實測約多5個百分點）。
  **判斷門檻用geometric版，不用simple版**——simple版只是給人一眼對得上
  總司令自己心算的那個數字，不是本表的判定依據，這裡明講不能兩個都
  拿來互相取代。

**成本模型來源**：呼叫既有`research/validation/costs.py::round_trip_cost_pct()`
（`CONSTITUTION.md`欽定的「真實摩擦全部計入」模組），不在這支重寫成本
公式。同時額外印出「不含滑價」版本（`0.1425%×2×折扣+0.3%`），因為
`.github/scripts/build_benchmark_comparison.py`目前App上線那張「我們vs
0050」卡片用的正是**不含滑價**的0.585%——**這是一個本輪順帶查出的誠實
揭露缺口**：App卡片的成本估計比研究紀律模組更樂觀，代表卡片上顯示的
差距（三榜全輸幅度）如果換算成含滑價版本只會更難看，不會更好看。

**折扣情境是示意值，非查證特定券商實際費率**：1.0x／0.6x／0.3x只是常見
的整數折扣級距示意，用來看敏感度，**不是總司令現有群益／國泰帳戶的
實際查證費率**——若要精確數字需要真的去查兩個券商的公告費率表，本輪
未做這件事，如實揭露。

**0050買進持有基準**：本表以「真buy-and-hold、年化成本≈0」為主要判定
基準（總司令本輪原話「0050買進持有幾乎零周轉」），對照組另外標示
「若比照我方節奏依序換手」的0050年化成本，只做參照，不是判定用值
（那條路徑是`build_benchmark_comparison.py`實際上線卡片用的簡化算法，
是為了讓兩條線同一個x軸對齊，不是模擬真實买进持有經濟含義）。

跑法：`python research/validation/breakeven_alpha_table.py`
（純本機計算，零外部請求，零成本，可重複執行）。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from research.validation.costs import (  # noqa: E402
    COMMISSION_RATE,
    SECURITIES_TX_TAX_NORMAL,
    round_trip_cost_pct,
)

OUT_PATH = ROOT / "research" / "breakeven_alpha_table.json"
TZ = timezone(timedelta(hours=8))
TRADING_DAYS_PER_YEAR = 252  # 沿用 build_benchmark_comparison.py::_calmar() 既有慣例

HOLDING_WINDOWS = [("t5", 5), ("t20", 20), ("t60", 60), ("t120", 120)]
DISCOUNT_SCENARIOS = [
    ("無折扣(1.0x)", 1.0),
    ("6折(0.6x)", 0.6),
    ("3折(0.3x)", 0.3),
]
# 0050買進持有單次成本（不含滑價，ETF流動性佳且此處只做真buy-hold的一次性
# 攤銷參考，不逐年重複進出，不套用折扣情境——沿用既有benchmark_comparison
# 卡片同一個常數，避免兩處各算一套造成使用者比對時對不起來）
BENCHMARK_0050_ONE_TIME_COST_PCT = 0.1425 * 2 + 0.1


def simple_annual_needed(per_trade_cost_pct: float, trades_per_year: float) -> float:
    """總司令原話的線性近似：次數 × 單次成本。"""
    return per_trade_cost_pct * trades_per_year


def geometric_annual_needed(per_trade_cost_pct: float, trades_per_year: float) -> float:
    """複利精確版：((1-c)**-N - 1)，判定門檻用這個。"""
    c = per_trade_cost_pct / 100.0
    if c >= 1:
        return float("nan")
    return ((1 - c) ** -trades_per_year - 1) * 100


def build() -> dict:
    windows_out = []
    for window, days in HOLDING_WINDOWS:
        trades_per_year = TRADING_DAYS_PER_YEAR / days
        scenarios = []
        for label, discount in DISCOUNT_SCENARIOS:
            cost_with_slippage = round_trip_cost_pct(commission_discount=discount) * 100
            cost_no_slippage = (COMMISSION_RATE * 2 * discount + SECURITIES_TX_TAX_NORMAL) * 100
            scenarios.append({
                "discount_label": label,
                "commission_discount": discount,
                "roundtrip_cost_pct_no_slippage": round(cost_no_slippage, 4),
                "roundtrip_cost_pct_with_slippage": round(cost_with_slippage, 4),
                "breakeven_per_trade_alpha_pct": round(cost_with_slippage, 4),
                "breakeven_annual_alpha_pct_simple": round(
                    simple_annual_needed(cost_with_slippage, trades_per_year), 2),
                "breakeven_annual_alpha_pct_geometric": round(
                    geometric_annual_needed(cost_with_slippage, trades_per_year), 2),
            })
        same_cadence_0050_cost = BENCHMARK_0050_ONE_TIME_COST_PCT * trades_per_year
        windows_out.append({
            "window": window,
            "holding_days": days,
            "trades_per_year": round(trades_per_year, 2),
            "scenarios": scenarios,
            "benchmark_0050_same_cadence_annual_cost_pct_reference_only": round(same_cadence_0050_cost, 2),
        })

    return {
        "meta": {
            "generated_at": datetime.now(TZ).isoformat(),
            "question": "不同持有期下，我方需要多少毛alpha（相對0050的超額原始報酬）才能在扣成本後打平0050買進持有",
            "primary_metric": "breakeven_annual_alpha_pct_geometric（複利精確版，判定門檻用這個，不是simple版）",
            "cost_model_source": "research/validation/costs.py::round_trip_cost_pct()（CONSTITUTION.md欽定真實摩擦模組，含0.1425%×2手續費＋0.3%證交稅＋預設5bps×2滑價）",
            "discount_scenarios_note": "1.0x/0.6x/0.3x為示意折扣級距，非查證群益/國泰實際公告費率",
            "benchmark_0050_assumption": "主判定基準＝真buy-and-hold、年化成本≈0（一次性0.385%攤銷到長期趨近於0）；表內另附「若比照我方節奏換手」的參考值，僅供對照，非判定用",
            "known_honest_gap": "App上線中的「我們vs0050」卡片（.github/scripts/build_benchmark_comparison.py）用的0.585%單趟成本不含滑價，比本表含滑價版本更樂觀——代表卡片上的落後幅度换算成真實摩擦後只會更難看",
            "trading_days_per_year_assumption": TRADING_DAYS_PER_YEAR,
        },
        "holding_periods": windows_out,
    }


def main() -> int:
    payload = build()
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已寫入 {OUT_PATH.relative_to(ROOT)}")
    print()
    header = f'{"窗口":<6}{"年化次數":>8}{"折扣情境":<14}{"單趟成本%":>10}{"年化需求%(簡單)":>16}{"年化需求%(複利)":>16}'
    print(header)
    print("-" * len(header))
    for w in payload["holding_periods"]:
        for i, s in enumerate(w["scenarios"]):
            window_label = w["window"] if i == 0 else ""
            trades_label = f'{w["trades_per_year"]:.1f}' if i == 0 else ""
            print(f'{window_label:<6}{trades_label:>8}{s["discount_label"]:<14}'
                  f'{s["roundtrip_cost_pct_with_slippage"]:>10.4f}'
                  f'{s["breakeven_annual_alpha_pct_simple"]:>16.2f}'
                  f'{s["breakeven_annual_alpha_pct_geometric"]:>16.2f}')
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
