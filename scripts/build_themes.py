# -*- coding: utf-8 -*-
"""題材成員驗證與上線（題材庫實作二，2026-09-08）。

**種子表是 D 級（模型推斷），本身不能上線。** 這支負責把候選逐一拿去對
「已合規上線的管線」找證據，只有找到證據的才寫進 `data/themes.json` 對外顯示。

證據等級（總司令定義，門檻不放寬）：
- **A 級**＝公司自述：MOPS 重大訊息（TWSE `t187ap04_L`／TPEx `mopsfin_t187ap04_O`）
  與法說會公告。這些落在 `data/events.json`（建置一.1 已上線）。
- **C 級**＝新聞陳述：`data/news.json` 標題／內文命中，**且需 ≥2 篇獨立報導**。
  「獨立」定義為**不同的來源網域**——同一家媒體改標題重發不算兩篇。
- **D 級**＝模型推斷，**永不單獨顯示**，只留在種子檔當搜尋範圍。

**append-only 鐵律**：既有 `themes.json` 的 membership 一律保留原本的
`effective_from`，**禁止回頭改寫歷史歸屬**。新證據只會新增或升級等級，
不會竄改既有生效日——任何用到題材的回測必須以「該日已生效的歸屬」為準。
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".github" / "scripts"))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data"
SEED = D / "seed" / "seed_themes_validated.json"
OUT = D / "themes.json"
TZ = timezone(timedelta(hours=8))

MIN_C_REPORTS = 2      # C 級需要幾篇「不同來源」的獨立報導


def _load(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def main() -> int:
    seed = _load(SEED)
    if not seed:
        print(f"! 找不到 {SEED.name}，先跑 scripts/validate_seed_themes.py")
        return 1
    themes = seed.get("themes") or []
    news = (_load(D / "news.json", {}) or {}).get("news") or []
    events_doc = _load(D / "events.json", {}) or {}
    events = events_doc.get("events") or []
    prior = _load(OUT, {}) or {}
    prior_ms = {(m["code"], m["theme_id"]): m
                for m in (prior.get("memberships") or [])}

    try:
        from news_matcher import load_company_names, load_active_codes, match_article
        name2code, _amb = load_company_names()
        active = load_active_codes()
    except Exception as e:  # noqa: BLE001
        print(f"! news_matcher 載入失敗（{type(e).__name__}: {e}）")
        return 1

    # ── 事件索引：code → [事件]（A 級來源）────────────────────────────────
    ev_by_code = defaultdict(list)
    for e in events:
        c = e.get("code")
        if c:
            ev_by_code[c].append(e)

    # ── 新聞索引：先算出每則新聞命中哪些個股（用精確比對器）──────────────
    news_hits = []
    for n in news:
        m = match_article(n.get("title", ""), n.get("body", ""), name2code, active)
        if m["codes"]:
            news_hits.append((n, set(m["codes"]), n.get("title", "")))

    today = datetime.now(TZ).strftime("%Y-%m-%d")
    memberships = []
    stats = {"A": 0, "C": 0, "D_only": 0}
    themes_with_member = set()

    for t in themes:
        tid, kws = t["id"], [k for k in (t.get("kw") or []) if k]
        for code in t["members"]:
            ev_level, evidence = None, []

            # A 級：MOPS 重大訊息／法說會，且標題含此題材任一關鍵詞
            for e in ev_by_code.get(code, []):
                title = e.get("title", "") or ""
                if any(k and k in title for k in kws):
                    ev_level = "A"
                    evidence.append({"level": "A", "type": e.get("type"),
                                     "date": e.get("date"), "url": e.get("url"),
                                     "quote": title[:120]})
                    if len(evidence) >= 3:
                        break

            # C 級：新聞命中此股 + 標題含關鍵詞，且需 >=2 個不同來源網域
            if ev_level != "A":
                srcs, c_ev = set(), []
                for n, codes, title in news_hits:
                    if code not in codes:
                        continue
                    if not any(k and k in title for k in kws):
                        continue
                    dom = urlparse(n.get("url", "")).netloc
                    srcs.add(dom)
                    c_ev.append({"level": "C", "source": n.get("source"),
                                 "date": (n.get("published") or "")[:16],
                                 "url": n.get("url"), "quote": title[:120]})
                # 「獨立」＝不同網域。同一家媒體改標題重發不算兩篇。
                if len(srcs) >= MIN_C_REPORTS:
                    ev_level = "C"
                    evidence = c_ev[:3]

            key = (code, tid)
            if ev_level:
                stats[ev_level] += 1
                themes_with_member.add(tid)
                # append-only：既有的生效日不動，只可能升級等級
                eff = prior_ms.get(key, {}).get("effective_from", today)
                memberships.append({
                    "code": code, "theme_id": tid, "level": ev_level,
                    "weight": None,          # 營收比重不可得時標 unknown，不假裝
                    "weight_note": "unknown（營收比重來源受條款封鎖，見 DATA_SOURCE_MAP）",
                    "effective_from": eff, "evidence": evidence,
                    "evidence_count": len(evidence),
                })
            else:
                stats["D_only"] += 1

    doc = {
        "meta": {
            "generated_at": datetime.now(TZ).isoformat(),
            "seed": "data/seed/seed_themes_validated.json（D 級模型推斷，僅作搜尋範圍）",
            "evidence_rule": "A＝MOPS 重大訊息／法說會（公司自述）；"
                             f"C＝新聞陳述且需 ≥{MIN_C_REPORTS} 個不同來源網域；"
                             "D＝模型推斷，永不單獨顯示",
            "append_only": "memberships 的 effective_from 一律沿用既有值，禁止改寫歷史歸屬",
            "disclosure": "本題材庫由公開資訊與模型推斷建立、以公司公開文件與新聞驗證；"
                          "未收錄不代表無關聯。",
            "themes_total": len(themes),
            "themes_with_verified_member": len(themes_with_member),
            "members_A": stats["A"], "members_C": stats["C"],
            "candidates_unverified_D": stats["D_only"],
        },
        "themes": [{k: v for k, v in t.items() if k != "members_dropped"} for t in themes],
        "memberships": memberships,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    print("=" * 62)
    print("  題材成員首輪驗證（題材庫實作二）")
    print("=" * 62)
    print(f"  題材總數 {len(themes)}")
    print(f"  **至少一檔成員通過驗證的題材：{len(themes_with_member)}**")
    print(f"  通過的成員數：A 級 {stats['A']}、C 級 {stats['C']}"
          f"（合計 {stats['A'] + stats['C']}）")
    print(f"  仍為 D 級未驗證（不顯示）：{stats['D_only']}")
    print(f"  可用素材：事件 {len(events)} 筆、新聞 {len(news)} 則"
          f"（其中 {len(news_hits)} 則命中個股）")
    print(f"  → {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
