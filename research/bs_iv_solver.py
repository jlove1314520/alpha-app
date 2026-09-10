"""`HYPOTHESIS_QUEUE.md` #70 選擇權波動度偏斜（Volatility Skew）地基建置(b)：
Black-Scholes反推隱含波動度（IV）函式，並用教科書已知案例+round-trip網格
交叉驗證正確性。

**為什麼不能「寫完看數字順眼就直接信」（`HYPOTHESIS_QUEUE.md` #70條目
已知風險第1點要求）**：IV反推是數值方法（求根），任何一個環節寫錯
（d1/d2公式符號、N()用了pdf不是cdf、T用日曆天沒除以365.25、r沒有轉成
小數、Brent法上下界設反）都可能讓求根器「收斂」到一個看似合理但錯誤的
數字，不會報錯，只會安靜地產出雜訊——這正是`CLAUDE.md`研究紀律一再
強調的「工程正確性是可信度的一部分」。

**驗證方法（兩層，缺一不可）**：
1. **教科書案例**（外部真值，非自己算出來的）：Hull《Options, Futures,
   and Other Derivatives》第15章經典例題——S0=42, K=40, r=10%
   （連續複利）, T=0.5年, sigma=20% → Black-Scholes call價格應為
   **4.76**（教科書公認數字，非本模組自行計算）。本模組先用自製的
   `black_scholes_price()`算出這組參數的call價格，確認與4.76在合理
   精度內一致（驗證正向定價公式本身沒寫錯），再把算出的價格丟進
   `implied_vol()`反推，確認能收斂回sigma=20%（驗證反推求根器本身
   沒寫錯）。
2. **round-trip網格（兩層）**：先用已知sigma正向算價格，再反推，檢查
   能否在極小容忍度內（1e-6絕對誤差）收斂回原始sigma。
   (a) **核心範圍（必須100%通過，PASS/FAIL判準）**：只測**方向正確
       的OTM組合**（call僅K>=S、put僅K<=S，因為`#70`的選取邏輯本來
       就只會對「明確價外」合約呼叫`implied_vol()`，從不會對ITM合約
       呼叫），涵蓋近月（10~45天，比照#70 DTE_BAND）、近價平到中度
       價外（moneyness最遠15%）、實際可能觀測到的台指波動度（8%~
       80%）。864組全數通過。
   (b) **延伸壓力測試（僅診斷，不列入判準）**：刻意涵蓋深度ITM/OTM
       （moneyness最遠30%，含ITM方向）+短天期+極低波動（<=5%）等
       #70永遠不會實際遇到的極端組合，1008組中93組（9.2%）反推失敗，
       已用獨立診斷確認是**浮點數精度極限**（該類組合的時間價值遠
       小於內在價值的雙精度浮點解析度，例如同一價格對sigma從1e-6到
       0.10四捨五入後完全相同，任何求根器在這種輸入下都無法可靠
       反推），是數學上的病態問題（ill-posed）不是本模組邏輯錯誤，
       且這個區間本就不在#70的實際選取範圍內，誠實記錄但不影響PASS
       結論。

**已知簡化（誠實揭露，非藏起來）**：
- **股利率q=0**（未建模台指連續股利率）——`#70`資料可行性查證段落
  未查證台指的股利率資料源，正向定價公式與反推函式目前假設q=0。
  這會讓深度價內/價外選擇權的反推IV有系統性小幅偏誤（尤其call價格
  理論上因股利而略低於q=0假設下的公式值），但**skew本身是OTM put
  IV減OTM call IV的「差值」**，若q對兩者造成的偏誤方向相近，差值的
  誤差會部分抵消——這是留給下一輪組裝skew時序時需要留意並在文件裡
  註明的已知限制，不在本輪(b)展開處理（本輪聚焦「反推函式本身寫對
  了沒有」，不是「模型有沒有納入所有已知細節」，兩者是不同層次的
  問題，避免任務範疇蔓延）。
- 用連續複利利率（`r`需先從`cbc_rf_rate_client.py`回傳的年化百分比
  轉換：`r_continuous = ln(1 + r_pct/100)`，因為定存利率是年複利報價
  慣例，Black-Scholes公式要求連續複利——這個轉換將在(d)組裝skew時序
  時套用，本輪(b)的驗證用例直接給定連續複利r，不涉及這層轉換）。

2026-09-10由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程接續，佇列#70地基
建置(b)。全程零API呼叫（純數學/數值方法，無需任何外部資料）。
`is_holdout_consumed()`本輪開工/收工前皆確認`False`（本模組本身不觸碰
任何holdout資料）。
"""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm

# Brent法IV搜尋的波動度上下界（年化，小數）。下界避免sigma=0時d1/d2除以零；
# 上界500%已遠超任何台指選擇權實際會出現的隱含波動度，給足安全邊界。
_IV_LOWER = 1e-6
_IV_UPPER = 5.0
_ROUND_TRIP_TOL = 1e-6  # round-trip驗證的絕對誤差容忍度


def black_scholes_price(S: float, K: float, T: float, r: float, sigma: float, option_type: str) -> float:
    """Black-Scholes-Merton歐式選擇權定價（q=0，未建模股利率，見本檔
    docstring「已知簡化」段落）。option_type: 'call' 或 'put'。

    S: 標的現價；K: 履約價；T: 到期年數（日曆天/365.25）；r: 連續複利
    無風險利率（小數，非百分比）；sigma: 年化波動度（小數，非百分比）。
    """
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        raise ValueError(f"參數必須為正數: S={S}, K={K}, T={T}, sigma={sigma}")
    sqrt_t = math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t
    if option_type == "call":
        return S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    elif option_type == "put":
        return K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    else:
        raise ValueError(f"option_type必須是'call'或'put'，收到: {option_type}")


def implied_vol(price: float, S: float, K: float, T: float, r: float, option_type: str) -> float:
    """用Brent法（`scipy.optimize.brentq`）反推隱含波動度。選Brent法而非
    Newton-Raphson的理由：Brent法只需要一個連續函式+已知變號區間即可
    保證收斂，不需要解析vega、對深度價外合約（vega接近零、Newton法在
    這種情況容易發散或收斂極慢）更穩健——這正是#70會大量用到的場景
    （OTM put/call）。

    若price超出[理論最小值(內在價值), 理論最大值(sigma=_IV_UPPER時的
    價格)]區間，代表輸入資料本身有問題（例如過期報價/資料錯誤），
    本函式直接拋出`ValueError`而非靜默回傳邊界值，呼叫端須自行決定
    是否捨棄該筆觀測——比照`CLAUDE.md`「失敗要記錄原因分類，禁止靜默
    記None」。
    """
    def objective(sigma: float) -> float:
        return black_scholes_price(S, K, T, r, sigma, option_type) - price

    lo_val = objective(_IV_LOWER)
    hi_val = objective(_IV_UPPER)
    if lo_val * hi_val > 0:
        raise ValueError(
            f"price={price:.6f}超出[sigma={_IV_LOWER}, sigma={_IV_UPPER}]對應的理論價格區間"
            f"[{black_scholes_price(S, K, T, r, _IV_LOWER, option_type):.6f}, "
            f"{black_scholes_price(S, K, T, r, _IV_UPPER, option_type):.6f}]，"
            f"無法在合理波動度範圍內求解（S={S}, K={K}, T={T}, r={r}, type={option_type}）"
        )
    return float(brentq(objective, _IV_LOWER, _IV_UPPER, xtol=1e-10, rtol=1e-12, maxiter=200))


def cbc_pct_to_continuous_rate(rate_pct: float) -> float:
    """把`cbc_rf_rate_client.py`回傳的年化百分比定存利率（年複利報價
    慣例）轉換成Black-Scholes公式要求的連續複利利率。見本檔docstring
    「已知簡化」段落第2點。"""
    return math.log(1.0 + rate_pct / 100.0)


# ---------------------------------------------------------------------------
# 交叉驗證（本檔可直接執行，`python bs_iv_solver.py`）
# ---------------------------------------------------------------------------

def _test_hull_textbook_case() -> bool:
    """Hull教科書經典例題：S0=42, K=40, r=10%, T=0.5, sigma=20% →
    call價格應為4.76（教科書公認外部真值）。"""
    S, K, T, r, sigma_true = 42.0, 40.0, 0.5, 0.10, 0.20
    price = black_scholes_price(S, K, T, r, sigma_true, "call")
    print(f"[教科書案例] Hull S={S},K={K},r={r},T={T},sigma={sigma_true} "
          f"→ 算出call價格={price:.4f} (教科書公認值=4.76)")
    forward_ok = abs(price - 4.76) < 0.01
    print(f"  正向定價公式與教科書值誤差<0.01: {forward_ok}")

    recovered_sigma = implied_vol(price, S, K, T, r, "call")
    invert_ok = abs(recovered_sigma - sigma_true) < 1e-6
    print(f"  反推IV: {recovered_sigma:.8f} (真值={sigma_true}) 誤差={abs(recovered_sigma - sigma_true):.2e}")
    print(f"  反推收斂回原始sigma(誤差<1e-6): {invert_ok}")
    return forward_ok and invert_ok


def _run_round_trip_grid(S_values, moneyness_values, dte_days_values, sigma_values, r_values, option_types):
    """共用的round-trip迴圈，回傳(total, failed_list)。"""
    total = 0
    failed = []
    for S in S_values:
        for m in moneyness_values:
            K = S * m
            for dte in dte_days_values:
                T = dte / 365.25
                for sigma_true in sigma_values:
                    for r in r_values:
                        for opt_type in option_types:
                            total += 1
                            price = black_scholes_price(S, K, T, r, sigma_true, opt_type)
                            try:
                                recovered = implied_vol(price, S, K, T, r, opt_type)
                                err = abs(recovered - sigma_true)
                                if err >= _ROUND_TRIP_TOL:
                                    failed.append((S, K, T, r, sigma_true, opt_type, price, recovered, err, "誤差超出容忍度"))
                            except ValueError as e:
                                failed.append((S, K, T, r, sigma_true, opt_type, price, None, None, str(e)))
    return total, failed


def _test_round_trip_realistic_range() -> bool:
    """**核心驗證，必須100%通過**：覆蓋#70實際會用到的參數區間——近月
    (DTE_BAND=[10,45]天，比照`vrp_gate.py`既有決定)、近價平**且方向
    正確的OTM**（call只測moneyness>=1.0即K>S的真OTM call、put只測
    moneyness<=1.0即K<S的真OTM put，因為`#70`的選取邏輯本來就只會
    對「明確價外」的合約反推IV，從不會對ITM合約呼叫`implied_vol()`，
    測ITM組合不是本函式實際會遇到的情境——本輪已用獨立診斷確認：同一
    (S,T,sigma)下改測ITM方向會在深度ITM+短天期+低波動時觸發floating-
    point flatness失敗，但那些組合#70永遠不會產生，測那個方向反而是
    測錯範圍，不是更嚴謹）、實際可能觀測到的台指波動度區間（8%~80%，
    涵蓋平靜市況到危機時期）、台幣定存利率量級（0%~2%）。這個範圍內
    任何round-trip失敗都代表求根器有bug，不得放行進(c)(d)。"""
    call_moneyness = [1.00, 1.02, 1.04, 1.07, 1.10, 1.15]  # OTM call: K>=S
    put_moneyness = [1.00, 0.98, 0.96, 0.93, 0.90, 0.85]  # OTM put: K<=S
    dte_days_values = [10, 20, 30, 45]
    sigma_values = [0.08, 0.15, 0.25, 0.40, 0.60, 0.80]
    r_values = [0.0, 0.005, 0.02]
    S = 18000.0

    total = 0
    failed = []
    for moneyness_values, opt_type in ((call_moneyness, "call"), (put_moneyness, "put")):
        t, f = _run_round_trip_grid(
            S_values=[S], moneyness_values=moneyness_values, dte_days_values=dte_days_values,
            sigma_values=sigma_values, r_values=r_values, option_types=[opt_type],
        )
        total += t
        failed.extend(f)

    print(f"\n[Round-trip核心驗證：#70實際操作範圍（僅測方向正確的OTM組合）] 總測試組合數: {total}")
    print(f"  失敗數: {len(failed)}")
    if failed:
        print("  失敗明細（核心範圍內任何一筆失敗都是bug，須修正才能進下一輪）:")
        for row in failed[:20]:
            S_, K_, T_, r_, sig_, ot_, price_, rec_, err_, reason_ = row
            print(f"    S={S_},K={K_:.0f},T={T_:.4f},r={r_},sigma_true={sig_},type={ot_},"
                  f"price={price_},recovered={rec_},err={err_},reason={reason_}")
    ok = len(failed) == 0
    print(f"  核心範圍全數round-trip通過(誤差<{_ROUND_TRIP_TOL}): {ok}")
    return ok


def _test_round_trip_extended_stress() -> None:
    """**診斷用途，不列入PASS/FAIL判準**：把範圍延伸到深度價內/價外+
    極短天期+極低波動的組合，刻意涵蓋#70實際不會用到的極端區間，目的是
    誠實記錄求根器的已知數值極限（而非隱藏起來），供未來若有人想放寬
    #70的moneyness篩選範圍時參考。

    **已確認的已知限制（非bug）**：深度ITM/OTM（moneyness<=0.70或
    >=1.30）疊加極短天期（10天）+極低波動（<=5%）時，時間價值遠小於
    雙精度浮點數對內在價值的解析度（例如S=18000,K=12600,T=10/365.25
    情境下，sigma從1e-6到0.10價格皆四捨五入為完全相同的雙精度浮點數
    5400.0000000000——本輪已用獨立診斷腳本片段驗證，非本模組的邏輯
    錯誤），此時反推IV在數學上是病態問題（ill-posed，vega趨近於零），
    任何求根器都無法從這種價格可靠地反推出精確sigma。**這個區間本來就
    不在#70會用到的範圍內**（#70篩選的是「明確價外但仍有意義的流動性」
    履約價，不是深度價內/外的無時間價值合約），所以不影響`#70`的
    可用性，只是誠實記錄求根器的數學邊界在哪裡。
    """
    total, failed = _run_round_trip_grid(
        S_values=[18000.0],
        moneyness_values=[0.70, 0.85, 0.95, 1.00, 1.05, 1.15, 1.30],
        dte_days_values=[10, 20, 30, 45],
        sigma_values=[0.05, 0.10, 0.20, 0.35, 0.60, 1.00],
        r_values=[0.0, 0.005, 0.02],
        option_types=["call", "put"],
    )
    print(f"\n[Round-trip延伸壓力測試：涵蓋#70不會用到的極端區間，僅診斷，不列入PASS/FAIL]")
    print(f"  總測試組合數: {total}, 失敗數: {len(failed)} "
          f"({100.0 * len(failed) / total:.1f}%，預期集中在深度ITM/OTM+短天期+極低波動組合)")


def _test_rate_conversion() -> bool:
    """`cbc_pct_to_continuous_rate()`基本sanity：小利率時連續複利應
    略低於年複利報價（ln(1+x)<x for x>0），且對0應回傳0。"""
    zero_ok = cbc_pct_to_continuous_rate(0.0) == 0.0
    small_rate = cbc_pct_to_continuous_rate(0.725)  # 對照docstring範例：0.725%
    expected = math.log(1.00725)
    close_ok = abs(small_rate - expected) < 1e-12
    lower_than_pct = small_rate < 0.00725
    print(f"\n[利率轉換] cbc_pct_to_continuous_rate(0.725%) = {small_rate:.8f} "
          f"(手算ln(1.00725)={expected:.8f})")
    print(f"  數值一致: {close_ok}, 小利率時連續複利<年複利報價: {lower_than_pct}, 零值正確: {zero_ok}")
    return zero_ok and close_ok and lower_than_pct


def main() -> dict:
    print("=== #70地基建置(b)：Black-Scholes反推IV函式交叉驗證 ===")
    hull_ok = _test_hull_textbook_case()
    grid_ok = _test_round_trip_realistic_range()
    _test_round_trip_extended_stress()
    rate_ok = _test_rate_conversion()

    all_ok = hull_ok and grid_ok and rate_ok
    print(f"\n=== 總結 ===")
    print(f"  教科書案例(Hull)通過: {hull_ok}")
    print(f"  round-trip核心範圍(#70實際操作區間)全數通過: {grid_ok}")
    print(f"  round-trip延伸壓力測試: 僅診斷，見上方輸出（已知深度ITM/OTM+短天期+極低波動組合為病態問題，非bug，不影響本結論）")
    print(f"  利率轉換sanity通過: {rate_ok}")
    print(f"  地基建置(b)結論: {'PASS，反推函式可信任，下一輪可進(c)(d)' if all_ok else 'FAIL，反推函式有bug，不得進(c)(d)，須先修正'}")
    return {"hull_ok": hull_ok, "grid_ok": grid_ok, "rate_ok": rate_ok, "all_ok": all_ok}


if __name__ == "__main__":
    result = main()
    if not result["all_ok"]:
        raise SystemExit(1)
