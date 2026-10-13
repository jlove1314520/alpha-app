# -*- coding: utf-8 -*-
"""先.八十一-28（2026-10-13）：by_code 小檔與整份檔一致性自測。

抽樣（固定 2330／0050／00631L／8069 ＋ 亂數 60 檔，種子用當天日期）比對：
- 小檔各節（fundamentals／holders／institutional_history／foreign_holding／借券／cash_flow／sector_flow）裡這一檔的內容，
  與整份檔同一檔的內容完全相同；整份檔有、小檔沒有，或反過來，都算不一致。
- _meta.json 各節的共用欄位（meta 等）與整份檔相同（整份檔更新了、小檔沒重產就會不同）。
- scores：小檔那一列（去掉 _industry_pct）與 scores.json 同一列相同。
結果寫回 data/by_code/_meta.json 的 consistency 欄（checked_at、sample、mismatch、examples）。
mismatch>0 時 App 不用小檔、退回整份檔（app.js byCodeSection），並記進診斷 log。
排程：market.yml 在 build_by_code 之後跑；冒煙也跑。exit 1＝有不一致。用法：python scripts/selftest_by_code.py
"""
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import build_by_code as B  # noqa: E402

TW = timezone(timedelta(hours=8))
FIXED = ["2330", "0050", "00631L", "8069"]


def main() -> int:
    meta_p = B.OUT / "_meta.json"
    try:
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"讀不到 _meta.json（{type(e).__name__}）")
        return 1
    docs = {n: B._load(p) for n, p in B.SOURCES.items()}
    docs = {n: d for n, d in docs.items() if isinstance(d, dict)}
    sc = {r.get("code"): r for r in ((B._load(B.SCORES_FILE) or {}).get("stocks") or [])}
    codes = sorted(p.stem for p in B.OUT.glob("*.json") if not p.stem.startswith("_"))
    rnd = random.Random(datetime.now(TW).strftime("%Y%m%d"))
    sample = [c for c in FIXED if c in codes] + rnd.sample([c for c in codes if c not in FIXED], min(60, max(0, len(codes) - len(FIXED))))
    bad = []
    for n, d in docs.items():
        sec = (meta.get("sections") or {}).get(n) or {}
        for k, v in (sec.get("common") or {}).items():
            if d.get(k) != v:
                bad.append(f"_meta.{n}.{k} 與整份檔不同（整份檔可能已更新、小檔未重產）")
    for code in sample:
        try:
            small = json.loads((B.OUT / f"{code}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            bad.append(f"{code}：小檔讀不到")
            continue
        for n, d in docs.items():
            how = B.plan(d)
            part = small.get(n) or {}
            for k, h in how.items():
                if h == "dict":
                    full = d[k].get(code)
                    got = (part.get(k) or {}).get(code)
                    if full != got:
                        bad.append(f"{code}：{n}.{k} 不一致")
        if code in sc:
            row = dict(small.get("scores") or {})
            row.pop("_industry_pct", None)
            if row != sc[code]:
                bad.append(f"{code}：scores 列不一致")
    meta["consistency"] = {"checked_at": datetime.now(TW).isoformat(timespec="seconds"), "sample": len(sample),
                           "mismatch": len(bad), "examples": bad[:5]}
    meta_p.write_text(json.dumps(meta, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"by_code 一致性：抽樣 {len(sample)} 檔，不一致 {len(bad)} 處" + ("" if not bad else "；例：" + "；".join(bad[:3])))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
