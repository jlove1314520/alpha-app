# -*- coding: utf-8 -*-
"""先.一五六-2 ④ 國安基金第 10 次護盤事件：最優 2 版紙上追蹤（紙上優化軌）。

零外部請求：只讀 research/data/paper_8_taiex_closes.json（TWSE FMTQIK 官方收盤，market.yml 逐班累積）。
起點＝2026-11-09（宣布日 11/06 盤後 → 下一交易日 11/09 收盤進場），只用宣布後資料、不倒填。
規則與回測同一支（research/ntsf_event_study.py）：
- NTSF-A：2× 每日再平衡（≈00631L）＋移動停利 15%，最長 250 個交易日
- NTSF-B：3× 每日再平衡（理論值；台灣無 3× ETF，實作要用台指期）＋移動停利 10%，最長 250 個交易日
成本：進出各 手續費 0.1425%＋滑價 0.1%，出場加證交稅 0.1%；融資 2%/年、內扣 1%/年按日扣。
輸出：research/data/paper_opt_ntsf.json（本機帳本，不進公開 repo）。失敗只印警告、exit 0（十二節）。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "data" / "paper_8_taiex_closes.json"
OUT = ROOT / "data" / "paper_opt_ntsf.json"
ENTRY_DATE = "2026-11-09"
FEE, SLIP, TAX, FIN, EXP = 0.001425, 0.001, 0.001, 0.02, 0.01
VERSIONS = [
    {"id": "NTSF-A", "lev": 2.0, "trail": 0.15, "name": "國安基金護盤後 2×（≈00631L）移動停利 15%"},
    {"id": "NTSF-B", "lev": 3.0, "trail": 0.10, "name": "國安基金護盤後 3×（理論，台指期實作）移動停利 10%"},
]


def run() -> dict:
    closes = json.loads(SRC.read_text(encoding="utf-8"))["closes"]
    days = sorted(d for d in closes if d >= ENTRY_DATE)
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "entry_date": ENTRY_DATE,
           "source": "research/data/paper_8_taiex_closes.json（TWSE FMTQIK）", "versions": []}
    if not days or days[0] != ENTRY_DATE:
        out["error"] = f"沒有 {ENTRY_DATE} 收盤，無法起算"
        return out
    for v in VERSIONS:
        L = v["lev"]
        nav = 1 - FEE - SLIP
        peak = nav
        curve = [[ENTRY_DATE, round(nav, 5)]]
        status, exit_date = "持有中", None
        for i in range(1, len(days)):
            r = closes[days[i]] / closes[days[i - 1]] - 1
            nav *= 1 + L * r - (L - 1) * FIN / 252 - EXP / 252
            peak = max(peak, nav)
            if nav / peak - 1 <= -v["trail"] or i >= 250:
                nav *= 1 - FEE - SLIP - TAX
                status, exit_date = ("移動停利出場" if i < 250 else "滿 250 日出場"), days[i]
                curve.append([days[i], round(nav, 5)])
                break
            curve.append([days[i], round(nav, 5)])
        out["versions"].append({**v, "status": status, "exit_date": exit_date, "nav": round(nav, 5),
                                "peak": round(peak, 5), "days_held": len(curve) - 1, "curve": curve})
    return out


def main() -> int:
    try:
        out = run()
    except Exception as e:  # 十二節：只降級成警告
        print(f"[警告] paper_opt_ntsf 失敗：{e!r}")
        return 0
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for v in out.get("versions", []):
        print(v["id"], v["status"], "nav", v["nav"], "days", v["days_held"])
    if out.get("error"):
        print("[警告]", out["error"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
