"""用 git 歷史裡的 `data/short_lending_available.json` 快照，依新日期鍵規則重建
`data/short_lending_available_history.json`（先.一三五-1bt，零外部請求）。

舊累積器用 UTC 抓取日當鍵，05:43 班抓到的新數字會蓋掉前一天的真值、週末也會多出鍵；新鍵＝數字適用的交易時段日。
這支照時間順序重播每一份 commit 過的快照，套用 `accumulate_short_lending_available` 的
`date_key_for()`／`_accumulate()`，同一天多份快照以最後一份為準（同累積器）。
限制：沒 commit 過的中間抓取拿不回來；舊檔有、但重播後沒有的日期就是留缺口，不補。

用法：python scripts/rebuild_short_lending_history.py [--write]（不帶 --write 只印差異）
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".github" / "scripts"))
import accumulate_short_lending_available as SLA  # noqa: E402

SNAP_REL = "data/short_lending_available.json"


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", check=True).stdout


def snapshots() -> list[dict]:
    out, seen = [], set()
    for h in reversed(_git("log", "--format=%H", "--", SNAP_REL).split()):
        try:
            s = json.loads(_git("show", f"{h}:{SNAP_REL}"))
        except (subprocess.CalledProcessError, ValueError):
            continue
        fa = s.get("fetched_at")
        if not isinstance(s, dict) or not fa or fa in seen:
            continue
        seen.add(fa)
        out.append(s)
    out.sort(key=lambda s: s["fetched_at"])
    return out


def rebuild(snaps: list[dict], cal: dict) -> tuple[dict, dict, list[str]]:
    tw, otc, log = {}, {}, []
    for s in snaps:
        key, why = SLA.date_key_for(s["fetched_at"], cal)
        tmap, omap = s.get("twse") or {}, s.get("otc") or {}
        if key is None:
            log.append(f"{s['fetched_at']} 略過：{why}")
            continue
        if not tmap and not omap:
            log.append(f"{s['fetched_at']} 略過：空快照")
            continue
        tw, _ = SLA._accumulate(tw, tmap, key)
        otc, _ = SLA._accumulate(otc, omap, key)
        log.append(f"{s['fetched_at']} 記入 {key}")
    return tw, otc, log


def main() -> int:
    cal = json.loads((ROOT / "data" / "trading_calendar.json").read_text(encoding="utf-8"))
    snaps = snapshots()
    tw, otc, log = rebuild(snaps, cal)
    for line in log:
        print(" ", line)
    old = json.loads(SLA.OUT.read_text(encoding="utf-8")) if SLA.OUT.exists() else {}
    old_dates = sorted({d for b in (old.get("series_twse") or {}).values() for d in b})
    new_dates = sorted({d for b in tw.values() for d in b})
    print(f"快照 {len(snaps)} 份；舊檔日期 {len(old_dates)} 個、重建後 {len(new_dates)} 個")
    print("  只在舊檔：", [d for d in old_dates if d not in new_dates])
    print("  只在重建：", [d for d in new_dates if d not in old_dates])
    changed = [d for d in new_dates if d in old_dates
               and any((old["series_twse"].get(c) or {}).get(d) != b.get(d) for c, b in tw.items() if d in b)]
    print("  同日期但數字不同：", changed)
    if "--write" not in sys.argv:
        print("（未帶 --write，沒有寫檔）")
        return 0
    if not tw and not otc:
        print("! 重建結果是空的，不寫")
        return 1
    tdates = sorted({d for b in tw.values() for d in b})
    odates = sorted({d for b in otc.values() for d in b})
    meta = dict(old.get("meta") or {})
    meta.update({
        "generated_at": snaps[-1]["fetched_at"] if snaps else None,
        "date_key_caveat": SLA.DATE_KEY_CAVEAT,
        "rebuilt": "2026-10-30 先.一三五-1bt 用 git 歷史快照依新鍵規則重建（scripts/rebuild_short_lending_history.py）",
        "twse_dates_available": len(tdates), "twse_date_range": [tdates[0], tdates[-1]] if tdates else None,
        "otc_dates_available": len(odates), "otc_date_range": [odates[0], odates[-1]] if odates else None,
        "twse_stocks": len(tw), "otc_stocks": len(otc),
    })
    SLA.OUT.write_text(json.dumps({"meta": meta, "series_twse": tw, "series_otc": otc},
                                  ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"已寫 {SLA.OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
