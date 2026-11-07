# -*- coding: utf-8 -*-
"""先.一三五-1mx（2026-11-08）：全市場掃 stock_detail 季度「淨利÷EPS 推得股數」持續跳變的檔，
對照本機 BWIBBU 本益比×收盤價反推官方近四季 EPS，看「舊季 EPS÷倍數」後對不對得上。

零外部請求：只讀 data/stock_detail.json、data/fundamentals.json、data/quotes_all_tw.json。
判定邏輯與產生端 `.github/scripts/update_stock_financials.py::detect_share_base_shift()` 共用（直接 import）。
用法：python scripts/probe_eps_share_base_shift.py [--json 輸出路徑]
"""
import importlib.util
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception as e:  # 十二節：編碼設定失敗只警告
    print(f"[warn] stdout reconfigure 失敗：{e}")

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("usf", ROOT / ".github" / "scripts" / "update_stock_financials.py")
usf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(usf)


def main():
    detail = json.loads((ROOT / "data" / "stock_detail.json").read_text(encoding="utf-8"))
    official = usf.load_official_ttm_eps_map()
    rows = []
    for code, s in (detail.get("stocks") or {}).items():
        qs = ((s or {}).get("financials") or {}).get("quarters") or []
        try:
            r = usf.detect_share_base_shift(qs)
        except Exception as e:
            print(f"[warn] {code} 判定失敗：{e}")
            continue
        if not r:
            continue
        r["code"] = code
        r["official_ttm"] = official.get(code)
        r["verdict"] = usf.verify_share_base_shift(qs, r, official.get(code))
        rows.append(r)
    from collections import Counter
    c = Counter(x["verdict"]["status"] for x in rows)
    print(f"持續跳變檔數：{len(rows)}；判定分布：{dict(c)}")
    for x in sorted(rows, key=lambda z: z["code"]):
        v = x["verdict"]
        print(f"{x['code']} 跳變於 {x['break_at']} 倍數 {x['factor']:.3f}（舊 {x['old_shares']/1e6:,.1f}M → 新 {x['new_shares']/1e6:,.1f}M）"
              f" 官方TTM={x['official_ttm']} 我方舊={v.get('ttm_old')} 調整後={v.get('ttm_restated')} → {v['status']}")
    if "--json" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--json") + 1])
        out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
