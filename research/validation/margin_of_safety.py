# -*- coding: utf-8 -*-
"""
安全邊際情境（2026-09-19總司令裁示【#63邊緣案例＋安全邊際倍數重新錨定】二）。

取代`CONSTITUTION.md`原本「成本敏感度(1x/2x/3x)」的機械倍數規則。問題：
1.8折下2x(0.9026%)已經比「完全無折扣+滑價」(0.535~0.685%)還貴，3x
(1.3540%)是現實中不存在的情境——安全邊際的用意是「防我們對成本估錯」，
機械倍數卻變成「防一個不可能發生的世界」，且倍數越高、成本估得越準
反而讓門檻顯得越武斷。

改為三個錨定到具體、有解釋力的情境，全部呼叫`round_trip_cost_pct()`
現算，不得硬寫數字：
  基準情境：1.8折（總司令查證過的實際折數）+ 預設滑價
  保守情境：無折扣(1.0x，全額牌告費率) + 預設滑價
  最壞情境：無折扣 + 雙倍滑價

**判準**：構造必須在「最壞情境」下淨效益仍為正，取代舊的「必須撐過2x/3x」。

**日內沖銷 vs 一般交易的稅率要一致**：`daytrade`參數必須對應該構造實際的
交易型態（是否為現股當沖），三個情境要用同一個`daytrade`值計算，不可
在同一組情境比較中混用不同稅率假設（2026-09-19本次校正時發現裁示原文
自己舉的範例數字混用了兩種稅率，見`STRATEGY_GRAVEYARD.md` #63條目與
`PENDING_QUEUE.md`「安全邊際.一」的誠實揭露，已用本模組修正）。
"""
from __future__ import annotations

from validation.costs import DEFAULT_SLIPPAGE_BPS, round_trip_cost_pct

WORST_CASE_KEY = "最壞情境(無折扣+雙倍滑價)"
BASELINE_KEY = "基準情境(1.8折+預設滑價)"
CONSERVATIVE_KEY = "保守情境(無折扣+預設滑價)"


def margin_of_safety_scenarios(daytrade: bool = False) -> dict[str, float]:
    """回傳{情境名稱: round-trip成本百分比(小數，非乘以100)}。

    daytrade必須對應被測構造實際的交易型態——三個情境務必用同一個
    daytrade值，不可混用（現股當沖稅0.15% vs 一般交易稅0.3%）。
    """
    return {
        BASELINE_KEY: round_trip_cost_pct(
            daytrade=daytrade, slippage_bps=DEFAULT_SLIPPAGE_BPS, commission_discount=0.18),
        CONSERVATIVE_KEY: round_trip_cost_pct(
            daytrade=daytrade, slippage_bps=DEFAULT_SLIPPAGE_BPS, commission_discount=1.0),
        WORST_CASE_KEY: round_trip_cost_pct(
            daytrade=daytrade, slippage_bps=DEFAULT_SLIPPAGE_BPS * 2, commission_discount=1.0),
    }


def passes_worst_case(net_benefit_fn, daytrade: bool = False) -> dict:
    """`net_benefit_fn(cost_pct) -> float`：呼叫端傳入一個「給定round-trip成本
    百分比，回傳淨效益」的函式，這裡負責跑三個情境並判定最壞情境是否為正。
    回傳{情境名稱: {cost_pct, net_benefit}}，外加"verdict"欄位。
    """
    scenarios = margin_of_safety_scenarios(daytrade=daytrade)
    out = {}
    for name, cost_pct in scenarios.items():
        out[name] = {"cost_pct": cost_pct, "net_benefit": net_benefit_fn(cost_pct)}
    out["verdict"] = "PASS" if out[WORST_CASE_KEY]["net_benefit"] > 0 else "FAIL"
    return out
