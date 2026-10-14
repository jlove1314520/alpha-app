# -*- coding: utf-8 -*-
"""先.九十四-5b 自測：research/warrant_iv.py 合成價格往返、邊界情境不拋錯。

用法：python scripts/selftest_warrant_iv.py   （全過 exit 0）
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import warrant_iv as V  # noqa: E402

FAIL = []


def ok(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        FAIL.append(msg)


def main() -> int:
    # 1. 買權賣權平價（驗定價公式本身）
    S, K, T, r, s = 100.0, 95.0, 0.5, V.RISK_FREE, 0.3
    c, p = V.bs_price(S, K, T, s, "C"), V.bs_price(S, K, T, s, "P")
    ok(abs((c - p) - (S - K * math.exp(-r * T))) < 1e-10, f"買權賣權平價 C−P＝S−Ke^(−rT)（{c:.6f}−{p:.6f}）")
    ok(abs(V.bs_price(S, K, T, s, "C", ratio=0.065) - 0.065 * c) < 1e-12, "行使比例線性縮放")

    # 2. 合成價格往返：價格誤差 <1e-4，且 vega 不太小的格子 IV 誤差 <1e-4
    worst_p, worst_v, n = 0.0, 0.0, 0
    for cp in ("C", "P"):
        for m in (0.6, 0.8, 0.95, 1.0, 1.05, 1.25, 1.6):  # K/S
            for T in (7 / 365, 30 / 365, 0.25, 1.0):
                for s in (0.1, 0.3, 0.6, 1.2):
                    for ratio in (0.01, 0.1, 1.0):
                        K = 100 * m
                        price = V.bs_price(100.0, K, T, s, cp, ratio=ratio)
                        if price < 1e-6:  # 深價外、幾乎零價：IV 本來就不可辨識，只驗不拋錯（下面邊界測）
                            continue
                        iv, why = V.implied_vol(price, 100.0, K, T, cp, ratio=ratio)
                        if iv is None:
                            # 價格幾乎等於內含價值（深價內短天期）時，任何低波動都給同價：允許 None 但價格誤差仍要 <1e-4
                            intrinsic = V.bs_price(100.0, K, T, V.VOL_LO, cp, ratio=ratio)
                            worst_p = max(worst_p, abs(price - intrinsic))
                            continue
                        n += 1
                        worst_p = max(worst_p, abs(V.bs_price(100.0, K, T, iv, cp, ratio=ratio) - price))
                        vega = ratio * 100.0 * math.sqrt(T) * math.exp(-0.5 * ((math.log(100 / K) + (V.RISK_FREE + 0.5 * s * s) * T) / (s * math.sqrt(T))) ** 2) / math.sqrt(2 * math.pi)
                        if vega > 1e-3:
                            worst_v = max(worst_v, abs(iv - s))
    ok(n > 300 and worst_p < 1e-4, f"往返價格誤差最大 {worst_p:.2e} <1e-4（{n} 格反推成功）")
    ok(worst_v < 1e-4, f"vega>1e-3 的格子 IV 誤差最大 {worst_v:.2e} <1e-4")

    # 3. 邊界：不拋錯、回固定原因
    cases = {
        "到期日 0": (0.5, 100, 90, 0.0, "C"),
        "到期日為負": (0.5, 100, 90, -0.01, "P"),
        "深價內低於內含": (5.0, 100, 50, 0.1, "C"),     # 內含 ≈50，價格 5 → 低於內含
        "深價外": (1e-5, 100, 300, 0.05, "C"),
        "深價內認售": (60.0, 40, 100, 0.2, "P"),
        "價格 0": (0.0, 100, 100, 0.2, "C"),
        "價格過高": (500.0, 100, 100, 0.2, "C"),
        "缺值 None": (None, 100, 100, 0.2, "C"),
        "NaN": (float("nan"), 100, 100, 0.2, "C"),
    }
    for name, (pr, S_, K_, T_, cp) in cases.items():
        try:
            iv, why = V.implied_vol(pr, S_, K_, T_, cp)
            ok(why in ("ok", "缺值", "非正值", "已到期", "低於內含價值", "高於上限"), f"邊界「{name}」不拋錯（{why}，iv={iv}）")
        except Exception as e:  # noqa: BLE001
            ok(False, f"邊界「{name}」拋錯 {type(e).__name__}: {e}")
    ok(V.implied_vol(0.5, 100, 90, 0.0, "C")[1] == "已到期", "到期日 0 → 已到期")
    ok(V.implied_vol(500.0, 100, 100, 0.2, "C")[1] == "高於上限", "認購價格高於標的 → 高於上限")
    try:
        ok(V.bs_price(100, 90, 0.0, 0.3, "C") == 10.0 and V.bs_price(100, 90, 0.5, 0.0, "P") == 0.0,
           "bs_price 在 T＝0／σ＝0 回內含價值")
    except Exception as e:  # noqa: BLE001
        ok(False, f"bs_price 邊界拋錯 {e}")

    print(f"\n{'全部通過' if not FAIL else f'失敗 {len(FAIL)} 項'}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
