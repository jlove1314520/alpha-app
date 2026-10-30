# -*- coding: utf-8 -*-
"""先.八十一-9（2026-10-13）：選股頁清單用的精簡檔 scores*_list.json。

scores.json（價值成長榜）gzip 後約 520KB，八成是每檔每個因子的 raw（計算明細）與 reason（說明文字），
清單頁只需要總分、排名、各因子分數與百分位（同產業百分位、摘要句都只用這兩個）。這支把三榜各切一份
精簡清單：每列保留 factors.*.score／percentile，拿掉 raw／reason，列上加 _lite:true。
完整列（含 raw／reason）在展開或點進報告時才讀 data/by_code/<代號>.json（scripts/build_by_code.py）。
零外部請求、內容沒變不重寫。排程：market.yml 與 audit.yml 寫完 scores*.json 後各跑一次。
用法：python scripts/build_scores_list.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOARDS = ("scores", "scores_momentum", "scores_future")
KEEP_FACTOR = ("score", "percentile")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def lite(doc: dict) -> dict:
    rows = []
    for r in doc.get("stocks") or []:
        x = dict(r)
        x["factors"] = {k: {kk: f.get(kk) for kk in KEEP_FACTOR if kk in f}
                        for k, f in (r.get("factors") or {}).items() if isinstance(f, dict)}
        x["_lite"] = True
        rows.append(x)
    out = {k: v for k, v in doc.items() if k != "stocks"}
    out["stocks"] = rows
    out["_lite"] = "清單精簡版（scripts/build_scores_list.py）：因子只留 score／percentile，完整明細見 data/by_code/<代號>.json"
    return out


def main() -> int:
    rc = 0
    for b in BOARDS:
        src, dst = ROOT / f"{b}.json", ROOT / f"{b}_list.json"
        try:
            doc = json.loads(src.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            print(f"[warn] {src.name} 讀不到（{type(e).__name__}），{dst.name} 維持原狀")
            rc = 1
            continue
        if not isinstance(doc, dict) or not isinstance(doc.get("stocks"), list) or not doc["stocks"]:
            # 先.一三五-1cv：格式不對／stocks 是空的 → 不寫空清單蓋掉上一版，也不讓例外中斷後面幾榜
            print(f"[warn] {src.name} 格式不對或 stocks 是空的，{dst.name} 維持原狀")
            rc = 1
            continue
        txt = json.dumps(lite(doc), ensure_ascii=False, separators=(",", ":"))
        old = dst.read_text(encoding="utf-8") if dst.exists() else None
        if old != txt:
            dst.write_text(txt, encoding="utf-8")
        print(f"{dst.name}：{len(doc.get('stocks') or [])} 列，{len(txt.encode('utf-8')) // 1024}KB（原 {src.stat().st_size // 1024}KB）{'' if old != txt else '，內容沒變'}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
