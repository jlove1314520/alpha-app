"""融資維持率：本站算法 → 籌碼K口徑的校準（先.五十二-1 建立，先.五十三-A 改版）。

- 外部讀數 external_points：**只存總司令提供的籌碼K讀數**（不得抓取籌碼K網站）。檔內沒有時，
  以 research/MARGIN_RATIO_RECONCILE.md「外部（籌碼K）」那一列（同樣是總司令提供）作為初始值。
- 同日本站原值：優先用對帳報告「A 全部（我方現行）」同日重建值（分子分母同一天），
  其次 data/margin_maintenance.json、research/data/margin_backfill.json 中同日且非資料不完整的 ratio_pct。
- k＝各點「外部 ÷ 本站」平均；每點誤差＝|本站×k − 外部|（pp）。任一點 >0.5pp → warn（App 顯示「校準待更新」，只降級警告）。
- 股災段（2024-07-15～08-15、2025-03-01～05-31）若有外部讀數且誤差 >1pp → 改依「本站水位」分段校準（mode=segmented），
  否則股災段的換算值標「校準未驗證」。
- `python research/build_margin_calibration.py --apply`：同時把 ratio_pct_ck（＝round(ratio_pct×k, 1)）寫回
  data/margin_maintenance.json 與 research/data/margin_backfill.json（資料不完整的紀錄不算）。
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "research" / "MARGIN_RATIO_RECONCILE.md"
OUT = REPO / "data" / "margin_ratio_calibration.json"
HIST = REPO / "data" / "margin_maintenance.json"
BACKFILL = REPO / "research" / "data" / "margin_backfill.json"
TW = timezone(timedelta(hours=8))

WARN_PP = 0.5            # 任一點誤差超過→校準待更新
SEGMENT_PP = 1.0         # 股災段誤差超過→依水位分段校準
CRASH_RANGES = [("2024-07-15", "2024-08-15"), ("2025-03-01", "2025-05-31")]
LEVEL_BINS = [(0.0, 150.0), (150.0, 175.0), (175.0, 200.0), (200.0, 1e9)]   # 本站原值水位（%）


def _md_row(txt: str, label: str) -> dict[str, float]:
    """從對帳報告第三節表格取一列：{'2026-09-23': 170.4, ...}。"""
    head = re.search(r"\| 版本 \|(.+)\|\n", txt)
    row = re.search(r"\| " + re.escape(label) + r"[^|]*\|(.+)\|\n", txt)
    if not head or not row:
        return {}
    dates = [h.strip() for h in head.group(1).split("|")]
    vals = [v.strip() for v in row.group(1).split("|")]
    out = {}
    for d, v in zip(dates, vals):
        m = re.fullmatch(r"(\d{2})/(\d{2})", d)
        if m and re.fullmatch(r"[0-9.]+", v):
            out[f"2026-{m.group(1)}-{m.group(2)}"] = float(v)
    return out


def _load(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def site_values() -> dict[str, float]:
    """同日本站原值（分子分母同一天）。"""
    vals = {}
    for r in (_load(BACKFILL, {}) or {}).get("records", []) or []:
        if not r.get("data_incomplete") and r.get("ratio_pct") is not None:
            vals[r["date"]] = float(r["ratio_pct"])
    for r in _load(HIST, []) or []:
        if not r.get("data_incomplete") and r.get("ratio_pct") is not None:
            vals[r.get("margin_money_date") or r["date"]] = float(r["ratio_pct"])
    try:
        vals.update(_md_row(SRC.read_text(encoding="utf-8"), "A 全部"))   # 對帳報告同日重建值最優先
    except OSError:
        pass
    return vals


def in_crash(d: str) -> int | None:
    for i, (a, b) in enumerate(CRASH_RANGES):
        if a <= d <= b:
            return i
    return None


def _bin(v: float) -> int:
    for i, (lo, hi) in enumerate(LEVEL_BINS):
        if lo <= v < hi:
            return i
    return len(LEVEL_BINS) - 1


def k_for(site_pct: float, cal: dict) -> float | None:
    if not cal or cal.get("k") is None:
        return None
    if cal.get("mode") == "segmented" and cal.get("segments"):
        b = _bin(site_pct)
        seg = next((s for s in cal["segments"] if s["bin"] == b), None)
        if seg and seg.get("k") is not None:
            return float(seg["k"])
    return float(cal["k"])


def ck_value(site_pct, cal: dict) -> float | None:
    """本站原值 → 對齊籌碼K的值（四捨五入 1 位）；沒有校準或沒有原值回 None。"""
    if site_pct is None:
        return None
    k = k_for(float(site_pct), cal)
    return None if k is None else round(float(site_pct) * k, 1)


def ck_status(date: str, cal: dict) -> str:
    i = in_crash(date)
    if i is not None and not (cal.get("crash_verified") or {}).get(str(i)):
        return "校準未驗證"
    return "校準待更新" if cal.get("warn") else "已校準"


def build(existing: dict | None = None, sites: dict | None = None) -> dict:
    existing = existing if existing is not None else (_load(OUT, {}) or {})
    sites = sites if sites is not None else site_values()
    ext = existing.get("external_points")
    if not ext:
        seed = _md_row(SRC.read_text(encoding="utf-8"), "外部（籌碼K）") if SRC.exists() else {}
        ext = [{"date": d, "chipk_pct": v, "source": "總司令提供（MARGIN_RATIO_RECONCILE.md 外部列）"} for d, v in sorted(seed.items())]
    pts = []
    for p in ext:
        s = sites.get(p["date"])
        pts.append({**{k: p[k] for k in ("date", "chipk_pct", "source") if k in p},
                    "site_pct": s, "ratio": (round(p["chipk_pct"] / s, 5) if s else None)})
    usable = [p for p in pts if p["ratio"] is not None]
    if not usable:
        raise ValueError("沒有任何外部讀數找得到同日本站原值，無法校準")
    k = round(sum(p["ratio"] for p in usable) / len(usable), 4)
    cal = {"k": k, "ratio_mean": k, "mode": "global", "segments": []}
    for p in usable:
        p["err_pp"] = round(abs(p["site_pct"] * k - p["chipk_pct"]), 2)
    # 股災段誤差 >1pp → 依水位分段校準
    if any(in_crash(p["date"]) is not None and p["err_pp"] > SEGMENT_PP for p in usable):
        segs = []
        for b, (lo, hi) in enumerate(LEVEL_BINS):
            grp = [p for p in usable if _bin(p["site_pct"]) == b]
            segs.append({"bin": b, "site_lo": lo, "site_hi": hi if hi < 1e8 else None, "n": len(grp),
                         "k": round(sum(p["ratio"] for p in grp) / len(grp), 4) if grp else None})
        filled = [s for s in segs if s["k"] is not None]
        for s in segs:                                    # 沒有讀數的水位用最近水位的 k
            if s["k"] is None:
                s["k"] = min(filled, key=lambda f: abs(f["bin"] - s["bin"]))["k"]
                s["borrowed"] = True
        cal.update(mode="segmented", segments=segs)
        for p in usable:
            p["err_pp"] = round(abs(p["site_pct"] * k_for(p["site_pct"], cal) - p["chipk_pct"]), 2)
    crash_verified = {}
    for i, _ in enumerate(CRASH_RANGES):
        cp = [p for p in usable if in_crash(p["date"]) == i]
        crash_verified[str(i)] = bool(cp) and all(p["err_pp"] <= SEGMENT_PP for p in cp)
    max_err = max(p["err_pp"] for p in usable)
    dates = sorted(p["date"] for p in usable)
    cal.update({
        "generated_at": datetime.now(TW).isoformat(timespec="seconds"),
        "n_points": len(usable), "max_err_pp": max_err, "warn": max_err > WARN_PP,
        "date_from": dates[0], "date_to": dates[-1], "n_days": len(usable),
        "ratio_min": min(p["ratio"] for p in usable), "ratio_max": max(p["ratio"] for p in usable),
        "external_points": pts, "crash_ranges": CRASH_RANGES, "crash_verified": crash_verified,
        "warn_pp": WARN_PP, "segment_pp": SEGMENT_PP,
        "meaning": "對齊籌碼K ≈ 本站算法 × k（由總司令提供的籌碼K讀數與同日本站原值重算；誤差 >0.5pp 標校準待更新）",
        "source": "external_points 只存總司令提供的籌碼K讀數，未抓取籌碼K網站；本站原值見 MARGIN_RATIO_RECONCILE.md／margin_maintenance.json／margin_backfill.json",
    })
    return cal


def apply(cal: dict) -> tuple[int, int]:
    """把 ratio_pct_ck 寫回兩個資料檔（資料不完整的紀錄不算、並移除舊 ck）。"""
    hist = _load(HIST, [])
    n1 = 0
    for r in hist:
        if r.get("data_incomplete") or r.get("ratio_pct") is None:
            r.pop("ratio_pct_ck", None)
            continue
        r["ratio_pct_ck"] = ck_value(r["ratio_pct"], cal)
        n1 += 1
    HIST.write_text(json.dumps(hist, ensure_ascii=False, indent=2), encoding="utf-8")
    bf = _load(BACKFILL, None)
    n2 = 0
    if isinstance(bf, dict):
        for r in bf.get("records", []):
            if r.get("data_incomplete") or r.get("ratio_pct") is None:
                r.pop("ratio_pct_ck", None)
                r.pop("ck_status", None)
                continue
            r["ratio_pct_ck"] = ck_value(r["ratio_pct"], cal)
            r["ck_status"] = ck_status(r["date"], cal)
            n2 += 1
        for key in ("low_2025_04", "low_2024_08", "low_2024_07_08"):
            lo = bf.get(key)
            if isinstance(lo, dict) and lo.get("ratio_pct") is not None:
                lo["ratio_pct_ck"] = ck_value(lo["ratio_pct"], cal)
                lo["ck_status"] = ck_status(lo["date"], cal)
        BACKFILL.write_text(json.dumps(bf, ensure_ascii=False, indent=1), encoding="utf-8")
    return n1, n2


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    cal = build()
    OUT.write_text(json.dumps(cal, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"寫入 {OUT.name}：k={cal['k']} 模式={cal['mode']} 點數={cal['n_points']} 最大誤差={cal['max_err_pp']}pp warn={cal['warn']}")
    for p in cal["external_points"]:
        print(f"  {p['date']} 籌碼K {p['chipk_pct']} 本站 {p['site_pct']} 誤差 {p.get('err_pp')}pp")
    if "--apply" in sys.argv:
        n1, n2 = apply(cal)
        print(f"ratio_pct_ck 寫回：margin_maintenance {n1} 筆、margin_backfill {n2} 筆")
    return 0


if __name__ == "__main__":
    sys.exit(main())
