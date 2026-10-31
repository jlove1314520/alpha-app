# -*- coding: utf-8 -*-
"""先.一三五-1fn-a／收件匣 033：模擬 L「新發行」改版前後對照乾跑（零外部請求、不寫帳本、不算報酬）。

逐個本機權證快照日，用兩種定義各算一次「當天新發行認購權證檔數」：
- 改前：上市取當日行情 quotes_twse_call 第一次出現（只列有成交的權證）＋上櫃 issue_tpex type=認購。
- 改後：上市取掛牌名冊 basic_twse 第一次出現（cp＝認購、kind 以一般型開頭）＋上櫃同上
  ＝ research/paper_12_warrant_wave_tracker.calls_in()（PREREG 修訂 R1）。
另核對「被標新發行的上市權證，前一份完整快照的掛牌名冊裡是不是早就有」——改後必須是 0。
出現日索引寫在暫存目錄，正式檔 research/data/paper_12_appearances.json 不動。
用法：python scripts/dryrun_paper_12_appearance_rule.py
非投資建議。
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))

import paper_12_warrant_wave_tracker as L  # noqa: E402


def old_calls(d: str) -> dict:
    """改版前的 calls_in()（上市 quotes_twse_call）。"""
    out = {}
    for r in L._gz(L.SNAP / d / "quotes_twse_call.json.gz") or []:
        if r.get("code") and r.get("underlying"):
            out[str(r["code"])] = str(r["underlying"])
    for code, r in (L._gz(L.SNAP / d / "issue_tpex.json.gz") or {}).items():
        if (r or {}).get("type") == "認購" and r.get("underlying_code"):
            out[str(code)] = str(r["underlying_code"])
    return out


def basic_codes(d: str) -> set:
    return {str(r.get("code")) for r in (L._gz(L.SNAP / d / "basic_twse.json.gz") or []) if r.get("code")}


def main() -> int:
    dates = sorted(p.name for p in L.SNAP.iterdir() if p.is_dir() and len(p.name) == 10 and p.name[4] == "-")
    dates = [d for d in dates if L.snapshot_ok(d)]
    with tempfile.TemporaryDirectory() as td:
        new_doc = L.update_appearances(L.SNAP, Path(td) / "appear.json")
    tpex_codes = set()
    old_seen: dict = {}
    prev_basic: set | None = None
    print("日期        改前新發行  改後新發行  改前其中上市  改後其中上市  上市前一份名冊早已有（改前／改後）  名冊對不到標的")
    rows = []
    for i, d in enumerate(dates):
        oc = old_calls(d)
        tpex_codes |= {c for c, r in (L._gz(L.SNAP / d / "issue_tpex.json.gz") or {}).items()}
        old_new = [w for w in oc if w not in old_seen] if i else []
        for w, u in oc.items():
            old_seen.setdefault(w, u)
        new_new = [w for w, v in new_doc["warrants"].items() if v.get("first_seen") == d]
        o_tw = [w for w in old_new if w not in tpex_codes]
        n_tw = [w for w in new_new if w not in tpex_codes]
        o_pre = sum(w in prev_basic for w in o_tw) if prev_basic is not None else 0
        n_pre = sum(w in prev_basic for w in n_tw) if prev_basic is not None else 0
        um = new_doc.get("unmapped_by_date", {}).get(d)
        rows.append((d, len(old_new), len(new_new), len(o_tw), len(n_tw), o_pre, n_pre, um))
        tag = "（首批，不算）" if i == 0 else ""
        print(f"{d}  {len(old_new):>9}  {len(new_new):>9}  {len(o_tw):>11}  {len(n_tw):>11}  "
              f"{o_pre:>14}／{n_pre:<14}  {um}{tag}")
        prev_basic = basic_codes(d)
    bad = [r for r in rows[1:] if r[6] > 0]
    print(f"\n快照日 {len(dates)} 天；改後被標新發行、但前一份名冊早已有的上市權證：{sum(r[6] for r in rows[1:])} 檔"
          + ("（不合格）" if bad else "（合格：不再把已掛牌的權證誤判成新發行）"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
