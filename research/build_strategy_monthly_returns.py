# -*- coding: utf-8 -*-
"""先.五十九-B4：輸出 data/strategy_monthly_returns.json（公開檔，給 App 破億卡在瀏覽器內算達標機率）。

只含五個策略在 2003-07～2024-12 的**回測月報酬**，不含任何個人資料。日報酬沿用 R2（先.五十八-C）的
`win_probability_2026_10.series()`（同一套 #418／#421／#424／#430 口徑），這裡只把日報酬連乘成月報酬。
描述性輸出，不登記試驗。一次性產生；回測期間固定（2025 起保留資料已用盡，不讀），不需排程。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import win_probability_2026_10 as WP  # noqa: E402

OUT = HERE.parent / "data" / "strategy_monthly_returns.json"
KEEP = ["0050", "Bb-90", "S3-C6", "R1-A", "R1-C"]
SOURCES = {
    "0050": "0050 含息日報酬全持有（#418 load_all r_0050）",
    "Bb-90": "#418 Bb-90（0050 45%／00646 45%／00697B 10%，月底再平衡）",
    "S3-C6": "#424 C6＋S3 信用利差閘門，延後一個交易日（與紙.三 一致）",
    "R1-A": "#430 R1-A（0050 70%＋台股 2 倍 30%，閘門關改現金，延後一日）",
    "R1-C": "#430 R1-C（0050 50%＋台股 2 倍 50%，閘門關改現金，延後一日）",
}


def main() -> int:
    dates, S = WP.series()
    per = dates.dt.to_period("M")
    months = list(per.unique())
    mi = per.map({p: i for i, p in enumerate(months)}).to_numpy()
    out = {}
    for k in KEEP:
        d = np.asarray(S[k], float)
        out[k] = [round(float(np.prod(1.0 + d[mi == i]) - 1.0), 6) for i in range(len(months))]
    doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "label": "回測，非保證",
        "disclaimer": "回測月報酬（2003-07～2024-12），非保證、非投資建議。2025 年起樣本外未納入；R1 無樣本外驗證。"
                      "偏誤說明見 research/WIN_PROBABILITY_2026-10.md。",
        "months": [str(p) for p in months],
        "strategies": KEEP,
        "sources": SOURCES,
        "returns": out,
        "bias_note_url": "https://github.com/jlove1314520/alpha-app/blob/main/research/WIN_PROBABILITY_2026-10.md",
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    cagr = {k: round((np.prod(1 + np.array(v)) ** (12 / len(v)) - 1) * 100, 2) for k, v in out.items()}
    print(f"寫入 {OUT.name}：{len(months)} 個月（{months[0]}～{months[-1]}），年化 {cagr}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
