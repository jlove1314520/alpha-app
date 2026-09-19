# -*- coding: utf-8 -*-
"""打平0050所需毛alpha計算表（2026-09-15總司令裁示【持有期與成本結構重新
檢視】一.1原始建立；**2026-09-19總司令裁示【成本模型更正】全面重算**）。

**⚠️ 舊表高估成本，曾用於否決方向，本次更正**：舊版折扣情境最低只測到
3折(0.3x)，但總司令實際手續費是**1.8折(0.18x)**——舊表用的成本假設比
真實情況高估1.7~2.9倍，任何用舊表「損益兩平線未過」為由判FAIL或被前置
關卡擋掉的試驗，都建立在被高估的成本上，**必須逐條回頭複核**（見
`PENDING_QUEUE.md`「成本.二」條目的清查結果，不在這支腳本裡做）。

**要回答的問題（總司令原話）**：「不同持有期下，我們需要多少毛alpha才能
打平0050」——這張表直接決定「該不該繼續做高周轉選股」。背景是兩個獨立
發現指向同一件事：#243 regime overlay的MDD改善扣完切換成本只剩1.8%、
我們vs0050三榜全輸且t5周轉一年約50次×0.585%≈29%成本——毛報酬還行，
成本吃光。**這個0.585%本身就是本次要更正的高估數字之一**。

**核心邏輯（一句話）**：假設我方選股跟0050承擔同樣的市場曝險（貝他相同），
唯一的差異是我方頻繁進出、0050買進持有幾乎零周轉。那麼我方要net報酬
打平0050，每次換股至少要比0050多賺出「一次來回成本」，一年換手N次
就要多賺N次的份——**這正是「打平所需毛alpha」**。

**兩種年化算法，刻意都算、都印出來，不是只選一個**：
- `_simple`：總司令原話自己用的算法（次數×單次成本，線性近似）。
- `_geometric`：複利精確版——`((1-單次成本)**-年化次數 - 1)`。**這個數字
  一定比simple版更高**（複利對成本的侵蝕比線性加總更兇，要用複利報酬
  補回來也要更多），差距在t1/t5這種高周轉窗口尤其明顯。
  **判斷門檻用geometric版，不用simple版**——simple版只是給人一眼對得上
  總司令自己心算的那個數字，不是本表的判定依據，這裡明講不能兩個都
  拿來互相取代。

**成本模型來源**：呼叫既有`research/validation/costs.py::round_trip_cost_pct()`
（`CONSTITUTION.md`欽定的「真實摩擦全部計入」模組，本次**不修改該檔案
本身**——它已經有`daytrade`參數支援當沖減半稅率、`commission_discount`
參數支援任意折扣，本次只是這支消費腳本沒有用到正確的折扣值與當沖
情境，問題出在呼叫端不是模組本身）。同時額外印出「不含滑價」版本
（`0.1425%×2×折扣+證交稅`），因為`.github/scripts/build_benchmark_
comparison.py`目前App上線那張「我們vs0050」卡片用的正是**不含滑價**
的成本估計——App卡片的成本估計比研究紀律模組更樂觀，代表卡片上顯示的
差距如果換算成含滑價版本只會更難看，不會更好看，這個誠實揭露維持不變。

**折扣情境（2026-09-19更正）**：**1.8折(0.18x)是總司令查證過的實際
手續費折數，本次起改為主要判定情境**，1.0x/0.6x/0.3x保留當作敏感度
對照（不是總司令現有券商的實際費率，是常見整數折扣級距示意，這點
沿用舊版揭露不變）。

**當沖情境（2026-09-19新增）**：新增t1（現股當沖）窗口，稅率用
`costs.py`既有的`SECURITIES_TX_TAX_DAYTRADE`（0.15%，減半優惠稅率）。
**查證：現股當沖證交稅減半的現行法規、適用條件與有效期限**（≥3來源，
2026-09-19查證）：
1. 財政部賦稅署《總統今（2）日修正公布「證券交易稅條例」第2條之2及
   第12條條文》：https://www.dot.gov.tw/singlehtml/ch26?cntId=fde9d7d1546d4df8a4db96bf23e2f57c
2. 財政部全球資訊網《立法院今（31）日三讀通過「證券交易稅條例」第2條
   之2及第12條條文修正草案》：https://www.mof.gov.tw/singlehtml/384fb3077bb349ea973e7fc6f13b6974?cntId=163515032583410f91d2fab867e3b113
3. 自由財經《當沖降稅1/4生效 財部：無須先徵後退》：
   https://ec.ltn.com.tw/article/breakingnews/4911648
**結論**：現股當沖證交稅稅率**千分之1.5（0.15%，為正常稅率千分之3的
一半）**，總統於2025-01-02修正公布，**延長適用至民國116年12月31日
（西元2027年12月31日）**——`costs.py`的`SECURITIES_TX_TAX_DAYTRADE=
0.0015`常數本身數字正確，本次查證是補上法規依據與有效期限文件，
不是發現常數本身錯誤。**已知限制**：2027年底之後是否繼續延長未知，
若屆時未再修法延長，t1當沖情境的成本會回升到與波段相同的0.3%稅率，
這是本表2027-12-31之後需要重新確認的假設，不是永久保證。

**0050年化管理費（2026-09-19新增，總司令要求查證）**：查證結果（≥3來源，
2026-09-19）——0050採**累進費率**，規模越大平均費率越低，非單一固定
數字：
1. 鉅亨網《295萬人見證！0050規模飛越2兆元大關 經理費率降至0.0725%》
   （引述元大投信2025-01-23經金管會核准公開說明書修正：經理費首1000億
   0.15%／1000~5000億0.10%／5000億~1兆0.08%／超過1兆0.05%；保管費
   1兆以下0.03%／超過1兆部分0.025%）：https://news.cnyes.com/news/id/6479632
2. MoneyDJ理財網即時費率頁面：經理費0.15%、總管理費用率0.22%
   （含0.07%非管理費用）：https://www.moneydj.com/ETF/X/Basic/Basic0004.xdjhtm?etfid=0050.tw
3. 聯合新聞網《0050規模破1.5兆！經理費調降總費用率估探0.18%》：
   平均經理費<0.08%、保管費<0.03%，總費用率估0.18%~0.19%：
   https://udn.com/news/story/123006/9438602
**結論（誠實揭露數字對不上的原因，不是查錯，是快照時間點不同）**：
三個來源給出0.18%~0.22%不同數字，**原因是這是累進費率，隨基金規模
持續成長，加權平均費率會持續下降，三個來源的查詢時間點/引用的規模
快照不同**，不是彼此矛盾。本表採**0.18%**（較新、較低的快照，跟總司令
原文猜測的0.355%相比，實際費率遠低於猜測值，方向上代表0050這個基準
比想像中更便宜、更難打敗，不是更容易）。**[自行裁量]這個數字本表只
記錄不代入主要breakeven公式**：0050的年管理費已經反映在
`adjust.adjusted_price_series("0050")`的實際還原股價序列裡（ETF的NAV
本來就是費後淨值），`天條一.1`（`research/survival_constraint_
allocation_test.py`）等直接使用真實0050價格序列的分析不需要再扣一次，
重複扣會把0050的門檻壓得比現實更低、讓我方策略看起來更容易打敗
基準——這裡列出數字只是滿足總司令查證要求、供未來需要「理論指數vs
ETF包裝成本」比較時使用，不是本表判定公式的輸入。

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
    SECURITIES_TX_TAX_DAYTRADE,
    round_trip_cost_pct,
)

OUT_PATH = ROOT / "research" / "breakeven_alpha_table.json"
TZ = timezone(timedelta(hours=8))
TRADING_DAYS_PER_YEAR = 252  # 沿用 build_benchmark_comparison.py::_calmar() 既有慣例

# (視窗代號, 持有天數, 是否現股當沖) —— 2026-09-19新增t1當沖窗口
HOLDING_WINDOWS = [("t1", 1, True), ("t5", 5, False), ("t20", 20, False),
                   ("t60", 60, False), ("t120", 120, False)]
# 2026-09-19總司令裁示【成本模型更正】：1.8折是查證過的實際折數，改為主要
# 判定情境，放在清單第一位；1.0x/0.6x/0.3x保留當敏感度對照（示意值，非
# 查證特定券商費率，沿用舊版既有揭露）。
DISCOUNT_SCENARIOS = [
    ("1.8折(0.18x)＝實際折數", 0.18),
    ("無折扣(1.0x)", 1.0),
    ("6折(0.6x)", 0.6),
    ("3折(0.3x)", 0.3),
]
# 0050買進持有單次成本（不含滑價，ETF流動性佳且此處只做真buy-hold的一次性
# 攤銷參考，不逐年重複進出，不套用折扣情境——沿用既有benchmark_comparison
# 卡片同一個常數，避免兩處各算一套造成使用者比對時對不起來）
BENCHMARK_0050_ONE_TIME_COST_PCT = 0.1425 * 2 + 0.1
# 2026-09-19新增（總司令要求查證，見檔頭「0050年化管理費」段落）：僅供
# 記錄與未來參考，不代入下方任何breakeven計算（理由見檔頭說明）。
BENCHMARK_0050_ANNUAL_EXPENSE_RATIO_PCT_REFERENCE_ONLY = 0.18
BENCHMARK_0050_ANNUAL_EXPENSE_RATIO_SOURCES = [
    "鉅亨網(2026,引述元大投信2025-01-23經金管會核准公開說明書修正)："
    "https://news.cnyes.com/news/id/6479632",
    "MoneyDJ理財網即時費率頁面：https://www.moneydj.com/ETF/X/Basic/Basic0004.xdjhtm?etfid=0050.tw",
    "聯合新聞網(2026-04)：https://udn.com/news/story/123006/9438602",
]


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
    for window, days, daytrade in HOLDING_WINDOWS:
        trades_per_year = TRADING_DAYS_PER_YEAR / days
        tax_rate_pct = (SECURITIES_TX_TAX_DAYTRADE if daytrade else SECURITIES_TX_TAX_NORMAL) * 100
        scenarios = []
        for label, discount in DISCOUNT_SCENARIOS:
            cost_with_slippage = round_trip_cost_pct(daytrade=daytrade, commission_discount=discount) * 100
            cost_no_slippage = (COMMISSION_RATE * 2 * discount * 100) + tax_rate_pct
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
            "daytrade": daytrade,
            "securities_tx_tax_pct": tax_rate_pct,
            "trades_per_year": round(trades_per_year, 2),
            "scenarios": scenarios,
            "benchmark_0050_same_cadence_annual_cost_pct_reference_only": round(same_cadence_0050_cost, 2),
        })

    return {
        "meta": {
            "generated_at": datetime.now(TZ).isoformat(),
            "correction_note": "2026-09-19總司令裁示【成本模型更正】：舊表最低只測3折，總司令實際手續費"
                                "1.8折，舊表成本高估1.7~2.9倍，曾用於否決方向的判定需回頭複核，"
                                "見PENDING_QUEUE.md「成本.二」條目",
            "question": "不同持有期下，我方需要多少毛alpha（相對0050的超額原始報酬）才能在扣成本後打平0050買進持有",
            "primary_metric": "breakeven_annual_alpha_pct_geometric（複利精確版，判定門檻用這個，不是simple版），"
                               "折扣情境用「1.8折(0.18x)＝實際折數」那一列，不是無折扣(1.0x)",
            "cost_model_source": "research/validation/costs.py::round_trip_cost_pct()（CONSTITUTION.md欽定真實摩擦模組，"
                                  "含0.1425%×2手續費＋證交稅(波段0.3%/當沖0.15%)＋預設5bps×2滑價）",
            "discount_scenarios_note": "1.8折(0.18x)是總司令查證過的實際折數，為主要判定情境；"
                                        "1.0x/0.6x/0.3x為示意折扣級距對照，非查證群益/國泰實際公告費率",
            "daytrade_tax_halving_sources": [
                "財政部賦稅署：https://www.dot.gov.tw/singlehtml/ch26?cntId=fde9d7d1546d4df8a4db96bf23e2f57c",
                "財政部全球資訊網：https://www.mof.gov.tw/singlehtml/384fb3077bb349ea973e7fc6f13b6974?cntId=163515032583410f91d2fab867e3b113",
                "自由財經：https://ec.ltn.com.tw/article/breakingnews/4911648",
            ],
            "daytrade_tax_halving_expiry": "2027-12-31（民國116年12月31日，2025-01-02總統修正公布延長，"
                                            "屆時未再修法延長則當沖稅率回升至與波段相同的0.3%）",
            "benchmark_0050_annual_expense_ratio_pct_reference_only": BENCHMARK_0050_ANNUAL_EXPENSE_RATIO_PCT_REFERENCE_ONLY,
            "benchmark_0050_annual_expense_ratio_sources": BENCHMARK_0050_ANNUAL_EXPENSE_RATIO_SOURCES,
            "benchmark_0050_annual_expense_ratio_note": "採用累進費率，隨基金規模成長持續下降，三來源快照"
                                                          "0.18%~0.22%不一致是時間點差異非查證錯誤；此數字僅供"
                                                          "記錄，不代入下方breakeven計算（理由見檔頭說明：真實0050"
                                                          "價格序列已內含此費用，重複扣會低估基準門檻）",
            "benchmark_0050_assumption": "主判定基準＝真buy-and-hold、年化成本≈0（一次性0.385%攤銷到長期趨近於0）；"
                                          "表內另附「若比照我方節奏換手」的參考值，僅供對照，非判定用",
            "known_honest_gap": "App上線中的「我們vs0050」卡片（.github/scripts/build_benchmark_comparison.py）"
                                 "用的0.585%單趟成本不含滑價，比本表含滑價版本更樂觀——代表卡片上的落後幅度"
                                 "换算成真實摩擦後只會更難看",
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
