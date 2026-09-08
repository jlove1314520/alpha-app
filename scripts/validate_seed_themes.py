# -*- coding: utf-8 -*-
"""種子題材表校驗（題材庫實作一，2026-09-08）。

Cowork 產出的 `data/seed/seed_themes.json` **全部是 D 級（模型推斷）**，
用途是把驗證的搜尋範圍從「2,837 檔 × 全題材」縮小到「每題材數十檔」，
**不是可以直接顯示的資料**。

**第一件事是剔除壞代號。** Cowork 自查出至少五個非法代號
（`6market`、`4points`、`2income`、`6path`、`6胡`）且不保證只有這些——
這正是模型生成資料的典型失效樣態：**格式看起來對，內容是編的**。
所以這裡不信任任何一個代號，全部拿官方在市名冊 `listed_universe.json` 對一次。

規則（總司令指定）：
- 不在官方在市名冊者一律剔除並列出清單
- **同一代號歸屬多題材是正常的（多重歸屬），不去重**
- 同一題材內重複代號要去重
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "data" / "seed" / "seed_themes.json"
OUT = ROOT / "data" / "seed" / "seed_themes_validated.json"
REPORT = ROOT / "data" / "seed" / "seed_validation_report.md"
TZ = timezone(timedelta(hours=8))


def main() -> int:
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    uni = json.loads((ROOT / "data" / "listed_universe.json").read_text(encoding="utf-8"))
    active = set(uni.get("active") or [])
    try:
        companies = json.loads(
            (ROOT / "data" / "company_info.json").read_text(encoding="utf-8")).get("companies") or {}
    except (OSError, json.JSONDecodeError):
        companies = {}

    themes = seed.get("themes") or []
    raw_codes: set[str] = set()
    for t in themes:
        raw_codes |= set(t.get("members") or [])

    bad: dict[str, list] = {}          # 壞代號 → 出現在哪些題材
    kept_themes = []
    emptied = []
    for t in themes:
        seen = []
        for c in (t.get("members") or []):
            if c in seen:
                continue               # 同一題材內去重
            seen.append(c)
        good = [c for c in seen if c in active]
        for c in seen:
            if c not in active:
                bad.setdefault(c, []).append(t["id"])
        nt = dict(t)
        nt["members"] = good
        nt["members_dropped"] = [c for c in seen if c not in active]
        nt["evidence_level"] = "D"     # 明示：全部未驗證
        kept_themes.append(nt)
        if not good:
            emptied.append(t["id"])

    valid_codes = {c for t in kept_themes for c in t["members"]}
    doc = dict(seed)
    doc["themes"] = kept_themes
    doc["validation"] = {
        "validated_at": datetime.now(TZ).isoformat(),
        "roster": "data/listed_universe.json",
        "themes": len(kept_themes),
        "codes_raw": len(raw_codes),
        "codes_valid": len(valid_codes),
        "codes_dropped": len(bad),
        "themes_emptied": emptied,
        "note": "全部成員仍為 D 級（模型推斷），未經驗證，不得對外顯示。",
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")

    # ── 報告 ──────────────────────────────────────────────────────────────
    lines = [
        "# 種子題材表校驗報告",
        "",
        f"> {datetime.now(TZ).strftime('%Y-%m-%d %H:%M')}　"
        f"來源 `data/seed/seed_themes.json`（Cowork 產出，全部 D 級模型推斷）",
        "",
        "## 總表",
        "",
        "| 項目 | 數量 |",
        "|---|---|",
        f"| 題材數 | **{len(kept_themes)}** |",
        f"| 產業鏈數 | {len({t.get('chain') for t in kept_themes})} |",
        f"| 原始不重複代號 | {len(raw_codes)} |",
        f"| **校驗後有效代號** | **{len(valid_codes)}** |",
        f"| **剔除（不在官方在市名冊）** | **{len(bad)}** |",
        f"| 被清空的題材 | {len(emptied) if emptied else 0} |",
        "",
        "## 剔除清單（逐一列出，不是只列 Cowork 自查到的那五個）",
        "",
        "| 代號 | 出現在哪些題材 |",
        "|---|---|",
    ]
    for c in sorted(bad):
        lines.append(f"| `{c}` | {', '.join(bad[c])} |")
    lines += [
        "",
        "**判定依據**：`listed_universe.json` 的 `active` 名冊"
        f"（{len(active)} 檔）。不在名冊即剔除，不做任何猜測或修補。",
        "",
        "## 各題材校驗後成員數",
        "",
        "| 題材 | 產業鏈 | 段位 | 有效 | 剔除 |",
        "|---|---|---|---|---|",
    ]
    for t in sorted(kept_themes, key=lambda x: -len(x["members"])):
        drop = ", ".join(f"`{c}`" for c in t["members_dropped"]) or "—"
        lines.append(f"| {t['name']} | {t.get('chain','')} | {t.get('seg','')} "
                     f"| {len(t['members'])} | {drop} |")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("=" * 62)
    print("  種子題材表校驗（題材庫實作一）")
    print("=" * 62)
    print(f"  題材 {len(kept_themes)} 個｜產業鏈 {len({t.get('chain') for t in kept_themes})} 條")
    print(f"  原始代號 {len(raw_codes)} → **有效 {len(valid_codes)}**、剔除 {len(bad)}")
    print(f"  被清空的題材：{emptied or '無'}")
    print()
    print("  剔除清單（全部，不只 Cowork 自查的五個）：")
    for c in sorted(bad):
        nm = (companies.get(c) or {}).get("name", "")
        print(f"    {c:10s} {nm:8s} ← {', '.join(bad[c])}")
    print()
    print(f"  → {OUT.relative_to(ROOT)}")
    print(f"  → {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
