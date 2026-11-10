# -*- coding: utf-8 -*-
"""先.一五八-1（收件匣 042 A）紙上優化軌 F3／F5／F2 的一次性「種子＋回測基準線」——零外部請求。

做什麼：
  用 research/reaudit_optimized_batch1.py 同一套 simulate()（REAUDIT_END 延長到本機快取終點，同 先.一五五-2 的 ext2025 做法），
  以 REAUDIT_OPTIMIZED.md §3「①原最優組不重調」的參數算三條回測曲線，並核對 §3 表上的 2025 起段數字：
    F3 ma_days=50、bear_exposure=0.5、L=3、stop=0.1  → 2025 起 +109.4%／-35.9%
    F5 vol_win=60、hi_vol_exposure=0.25、L=1、stop=None → 2025 起 +22.4%／-7.4%
    F2 mix=B、w_eq=0.85、safe=IEF、gate=MA6m、L=1、stop=0.1 → 2025 起 +22.4%／-20.1%
  輸出（只在本機，research/data 不進 repo）：
    research/data/paper_opt/bt_regime.json：三條回測日曲線（App 虛線用）＋核對結果
    research/data/paper_opt/f5_vol_seed.json：0050 含息日報酬 2003～快取終點（F5 每日產生器算 expanding 中位數用）
封網：先把 FRED 快取效期拉長、再把 socket 換成會拋例外的版本，確保任何漏網的下載路徑都直接失敗（教訓見 C:/alpha/CLAUDE.md
  yfinance 一節 2026-11-07）。
用法：python research/paper_opt_regime_seed.py
非投資建議。
"""
from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _no_net(*a, **k):
    raise RuntimeError("paper_opt_regime_seed 封網：不送外部請求")


import fred_yield_curve_gate as FRED  # noqa: E402

FRED._CACHE_MAX_AGE_SECONDS = 10 ** 12
socket.socket.connect = _no_net  # type: ignore[assignment]
socket.create_connection = _no_net  # type: ignore[assignment]
os.environ["REAUDIT_END"] = "2099-12-31"
_argv = sys.argv
import reaudit_optimized_batch1 as B  # noqa: E402

sys.argv = _argv
OUT = HERE / "data" / "paper_opt"
EXPECT = {"F3": (1.094, -0.359), "F5": (0.224, -0.074), "F2": (0.224, -0.201)}


def build():
    px = B.PX["0050"]
    e3 = B.shift1(np.where(B.ma_signal(px, 50) > 0, 1.0, 0.5))
    r3 = B.simulate(np.column_stack([e3, 1.0 - e3]), ["0050", "CASH"], 3.0, 0.1, False)
    e5 = B.vol_signal(B.R["0050"], 60, 0.25)
    r5 = B.simulate(np.column_stack([e5, 1.0 - e5]), ["0050", "CASH"], 1.0, None, False)
    T2, a2 = B.alloc_target("B", 0.85, "IEF", B.gate("MA", 6))
    r2 = B.simulate(T2, a2, 1.0, 0.1, True)
    return {"F3": r3["r"], "F5": r5["r"], "F2": r2["r"]}


def seg(r: np.ndarray, start: str) -> tuple[float, float]:
    m = (B.DATES >= start).to_numpy()
    c = np.cumprod(1 + r[m])
    yrs = (B.DATES[m].iloc[-1] - B.DATES[m].iloc[0]).days / 365.25
    return float(c[-1] ** (1 / yrs) - 1), float((c / np.maximum.accumulate(c) - 1).min())


def main() -> int:
    rs = build()
    ds = [str(d.date()) for d in B.DATES]
    out = {"end": ds[-1], "curves": {}, "check": {}}
    for k, r in rs.items():
        g, m = seg(r, "2025-01-01")
        eg, em = EXPECT[k]
        ok = abs(g - eg) < 0.005 and abs(m - em) < 0.005
        out["check"][k] = {"cagr_2025": round(g, 4), "mdd_2025": round(m, 4), "expect": [eg, em], "ok": ok}
        print(f"{k} 2025 起 {g:+.1%}／{m:.1%}（表 {eg:+.1%}／{em:.1%}）→ {'對上' if ok else '對不上'}")
        out["curves"][k] = [round(float(x), 8) for x in r]
    out["dates"] = ds
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "bt_regime.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    tw = B.R["0050"]
    (OUT / "f5_vol_seed.json").write_text(json.dumps({"end": ds[-1], "dates": ds, "r_0050": [round(float(x), 10) for x in tw],
                                                      "note": "日曆＝台股∪美股（同 batch1 ext2025），美股日 r_0050＝0"},
                                                     ensure_ascii=False), encoding="utf-8")
    print(f"寫入 bt_regime.json／f5_vol_seed.json（至 {ds[-1]}）")
    return 0 if all(v["ok"] for v in out["check"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
