# -*- coding: utf-8 -*-
"""先.一三五-1at 自測：漲停鎖死邊界合成案例（1ar 找到的漏判型態）。

全部用合成數字，零外部請求、不讀真實價格、不寫任何帳本、不改任何追蹤程式或核心檔。
① `official_limit.OfficialLimits`＋`lock_status()`（模擬 J／N 修訂 R1 用的官方檔位版）四型都要判鎖漲停：
   a. 檔位取整後 +9.71% 一字鎖（1ar 實例 1303：前收 139 → 152.5）
   b. 除權息日：基準＝前收 × factor_applied（參考價）
   c. 減資恢復買賣日：基準＝ref_price
   d. 上櫃：前一交易日 TPEx 公告的次日漲停價優先於計算值（公告日對不上才退回計算）
② 現行 `paper_forward_events.locked_up()`（模擬 Q／R，前收 ±10%、不取整、不用參考價）把 a、b 判「沒鎖」＝**已知差異**，
   印 KNOWN_GAP、不算 FAIL；1ar-a 採甲改版後，把 a、b 的近似版斷言改成「判鎖」。
用法：python scripts/selftest_locked_up_boundaries.py
非投資建議。
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001 —— 主控台不支援時照舊輸出
    pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))

import paper_forward_common as C  # noqa: E402
import paper_forward_events as E  # noqa: E402
from official_limit import OfficialLimits, lock_status  # noqa: E402

FAIL: list[str] = []
KNOWN: list[str] = []
D0, D1 = "2026-06-19", "2026-06-22"  # 前一交易日、當日


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  {detail}" if detail else ""))
    if not cond:
        FAIL.append(name)


def flat(p):
    return {"open": p, "high": p, "low": p, "close": p}


def px_of(code, prev_close, today_px):
    return C.Px({code: [{"date": D0, **flat(prev_close)}, {"date": D1, **flat(today_px)}]})


def official(ol, code, prev_close, today_px):
    lim = ol.limits(code, D1, D0, prev_close)
    up, _ = lock_status(lim, today_px, today_px, today_px, today_px)
    return lim, up


def approx_info(name, code, prev_close, today_px, known_gap):
    got = E.locked_up(px_of(code, prev_close, today_px), code, D1)
    if known_gap and not got:
        KNOWN.append(name)
        print(f"KNOWN_GAP {name}：近似版 locked_up()＝False（官方檔位版＝True；1ar-a 改版後改成斷言判鎖）")
    elif known_gap:
        print(f"NOTE {name}：近似版已判鎖（差異消失，請把本案改成斷言）")
    else:
        print(f"INFO {name}：近似版 locked_up()＝{got}")


def main() -> int:
    empty = OfficialLimits(tpex_docs=[], exdiv={})

    # a. 檔位取整 +9.71% 一字鎖：139 × 1.1 = 152.9 → 0.5 檔位向下取整 = 152.5
    lim, up = official(empty, "1303", 139.0, 152.5)
    check("a 檔位取整：官方漲停價 152.5", lim is not None and abs(lim["up"] - 152.5) < 1e-9, str(lim))
    check("a 檔位取整：152.5 一字判鎖漲停", up)
    check("a 來源 calc／基準 raw_prev_close", lim and lim["src"] == "calc" and lim["base_src"] == "raw_prev_close")
    _, up2 = official(empty, "1303", 139.0, 152.0)
    check("a 反例：152.0（差一檔）不判鎖", not up2)
    approx_info("a 檔位取整 +9.71%", "1303", 139.0, 152.5, known_gap=True)

    # b. 除權息日：前收 100、factor 0.95 → 參考價 95 → 漲停 104.5（不是 110）
    ex = OfficialLimits(tpex_docs=[], exdiv={"events": {"2001": [{"ex_date": D1, "factor_applied": 0.95}]}})
    lim, up = official(ex, "2001", 100.0, 104.5)
    check("b 除權息：基準＝參考價 95", lim and lim["base_src"] == "exdiv_ref" and abs(lim["base"] - 95.0) < 1e-9, str(lim))
    check("b 除權息：漲停 104.5 一字判鎖", lim and abs(lim["up"] - 104.5) < 1e-9 and up)
    _, up_raw = official(empty, "2001", 100.0, 104.5)
    check("b 對照：不套參考價時 104.5 不判鎖", not up_raw)
    approx_info("b 除權息日 104.5", "2001", 100.0, 104.5, known_gap=True)

    # c. 減資恢復買賣日：前收 8.72、ref 10.1 → 10.1 × 1.1 = 11.11 → 0.05 檔位 = 11.10
    red = OfficialLimits(tpex_docs=[], exdiv={"reductions": {"1441": [{"resume_date": D1, "ref_price": 10.1}]}})
    lim, up = official(red, "1441", 8.72, 11.1)
    check("c 減資恢復：基準＝ref 10.1", lim and lim["base_src"] == "reduction_ref" and abs(lim["base"] - 10.1) < 1e-9, str(lim))
    check("c 減資恢復：漲停 11.10 一字判鎖", lim and abs(lim["up"] - 11.1) < 1e-9 and up)
    _, up_lo = official(red, "1441", 8.72, 10.15)
    check("c 反例：10.15（未達 11.10）不判鎖", not up_lo)
    approx_info("c 減資恢復 11.10", "1441", 8.72, 11.1, known_gap=False)

    # d. 上櫃公告價優先：前收 50 計算值 55.0，公告 55.5 → 用 55.5
    doc = {"data_date": D0, "rows": {"6001": [55.5, 45.0]}}
    tp = OfficialLimits(tpex_docs=[doc], exdiv={})
    lim, up = official(tp, "6001", 50.0, 55.5)
    check("d 上櫃：來源 tpex_official、漲停 55.5", lim and lim["src"] == "tpex_official" and abs(lim["up"] - 55.5) < 1e-9, str(lim))
    check("d 上櫃：55.5 一字判鎖", up)
    _, up_calc = official(tp, "6001", 50.0, 55.0)
    check("d 上櫃：55.0（計算值）在公告 55.5 下不判鎖", not up_calc)
    stale = OfficialLimits(tpex_docs=[{"data_date": "2026-06-18", "rows": {"6001": [55.5, 45.0]}}], exdiv={})
    lim, up = official(stale, "6001", 50.0, 55.0)
    check("d 公告日≠前一交易日 → 退回計算、來源 calc_tpex_missing", lim and lim["src"] == "calc_tpex_missing" and up, str(lim))
    approx_info("d 上櫃公告 55.5", "6001", 50.0, 55.5, known_gap=False)

    # 十二節：算不出 → None → 不判鎖
    check("缺前收 → None、不判鎖", empty.limits("1303", D1, D0, None) is None and lock_status(None, 1, 1, 1, 1) == (False, False))

    print(f"\n結果：FAIL {len(FAIL)}、KNOWN_GAP {len(KNOWN)}（已知差異不算失敗）")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
