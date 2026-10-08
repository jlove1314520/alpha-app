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
- 先.五十五（2026-10-08）：若本機有 CM 估 53 日對帳明細（research/data/margin_reconcile/cm_reconcile_detail.json，
  gitignore，外部逐日數值只在本機），依事前判定規則重建：全段 k 最大−最小 ≤0.01 → 單一 k（中位數）；
  否則依本站水位分段（<180、180–195、≥195）各取中位數（mode=segmented，段界寫在 segments 的 site_lo／site_hi）。
  repo 的校準檔只存 k、統計、段界、天數與來源說明，不存外部逐日數值。
  沒有本機明細時（例如雲端排程）不重建、沿用現有校準檔，避免把分段結果蓋回舊值。
  ratio_mean 刻意保留八日單一比值（已上線 App 以它顯示「八日對帳比值」），分段只影響 ratio_pct_ck。
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
CM_DETAIL = REPO / "research" / "data" / "margin_reconcile" / "cm_reconcile_detail.json"   # 本機 gitignore
CM_SPAN_LIMIT = 0.01                                        # 先.五十五 A4 事前判定門檻
CM_TIERS = [(None, 180.0), (180.0, 195.0), (195.0, None)]   # 先.五十五 A4 事前分段（本站水位 %）
CM_CRASH = ("2026-07-27", "2026-08-04")


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
    if cal.get("mode") == "segmented" and cal.get("segments") and "site_lo" in cal["segments"][0] \
            and cal.get("tier_scheme") == "cm_2026_10_08":
        for seg in cal["segments"]:
            lo, hi = seg.get("site_lo"), seg.get("site_hi")
            if (lo is None or site_pct >= lo) and (hi is None or site_pct < hi):
                return float(seg["k"])
        return float(cal["k"])
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


def ck_status(date: str, cal: dict, site_pct: float | None = None) -> str:
    i = in_crash(date)
    cm = cal.get("cm_calibration") or {}
    lo = (cm.get("level_range_measured") or [None])[0]
    if i is not None and lo is not None and site_pct is not None:
        # 先.五十五：股災段依實測水位範圍更新——落在實測水位內＝分段校準可用；低於實測最低水位＝仍未驗證
        return "分段校準（實測水位內）" if site_pct >= lo else f"校準未驗證（低於實測最低水位 {lo}%）"
    if i is not None and not (cal.get("crash_verified") or {}).get(str(i)):
        return "校準未驗證"
    return "校準待更新" if cal.get("warn") else "已校準"


def _st(xs: list[float]) -> dict:
    import statistics as st
    if not xs:
        return {"n": 0}
    return {"n": len(xs), "median": round(st.median(xs), 5), "min": round(min(xs), 5), "max": round(max(xs), 5),
            "span": round(max(xs) - min(xs), 5), "stdev": round(st.stdev(xs), 5) if len(xs) > 1 else 0.0}


def build_cm(existing: dict) -> dict:
    """先.五十五：用本機 CM 估對帳明細＋既有 8 筆讀數（同日去重）依事前規則重建。不寫入任何外部逐日數值。"""
    import statistics as st
    det = json.loads(CM_DETAIL.read_text(encoding="utf-8"))
    rows = [r for r in det["rows"] if "k" in r]
    new_dates = {r["date"] for r in rows}
    comb = [(r["date"], float(r["ours_pct"]), float(r["k"])) for r in rows]
    prev = [p for p in (existing.get("external_points") or []) if p.get("site_pct") and p.get("chipk_pct")]
    comb += [(p["date"], float(p["site_pct"]), p["chipk_pct"] / p["site_pct"]) for p in prev if p["date"] not in new_dates]
    ks = [c[2] for c in comb]
    span = max(ks) - min(ks)
    cal = dict(existing)
    overall = round(st.median(ks), 4)
    if span <= CM_SPAN_LIMIT:
        cal.update(mode="global", k=overall, segments=[], tier_scheme=None)
        errs = [abs(c[1] * overall - c[1] * c[2]) for c in comb]
    else:
        segs, errs = [], []
        for lo, hi in CM_TIERS:
            g = [c for c in comb if (lo is None or c[1] >= lo) and (hi is None or c[1] < hi)]
            if not g:
                continue
            k = round(st.median(c[2] for c in g), 4)
            e = [abs(c[1] * k - c[1] * c[2]) for c in g]
            errs += e
            segs.append({"site_lo": lo, "site_hi": hi, "k": k, "n": len(g), "max_err_pp": round(max(e), 2),
                         "level_range": [round(min(c[1] for c in g), 1), round(max(c[1] for c in g), 1)]})
        cal.update(mode="segmented", k=overall, segments=segs, tier_scheme="cm_2026_10_08")
    crash = [c[2] for c in comb if CM_CRASH[0] <= c[0] <= CM_CRASH[1]]
    other = [c[2] for c in comb if not (CM_CRASH[0] <= c[0] <= CM_CRASH[1])]
    max_err = round(max(errs), 2)
    lvl = [c[1] for c in comb]
    cal.update({
        "generated_at": datetime.now(TW).isoformat(timespec="seconds"),
        "n_points": len(comb), "n_days": len(comb), "max_err_pp": max_err, "warn": max_err > WARN_PP,
        "ratio_min": round(min(ks), 5), "ratio_max": round(max(ks), 5),
        "cm_calibration": {
            "source": "CMoney 估算（經籌碼K顯示）；53 日讀數由總司令提供，只存本機、不入 repo；另併入先前 8 日籌碼K讀數（同日去重）",
            "n_provided_cm": len(det["rows"]) + len(det.get("missing") or []), "n_used_cm": len(rows),
            "excluded_dates": [x["date"] for x in det.get("excluded") or []],
            "n_combined": len(comb), "decision_rule": f"全段 k 最大−最小 ≤{CM_SPAN_LIMIT} → 單一 k；否則依本站水位 {CM_TIERS} 分段取中位數（事前固定）",
            "decision": cal["mode"], "k_all": _st(ks), "k_crash_0727_0804": _st(crash), "k_other": _st(other),
            "level_range_measured": [round(min(lvl), 1), round(max(lvl), 1)],
        },
        "meaning": "對齊籌碼K ≈ 本站算法 × k（依本站水位分段；段界與各段 k 見 segments）" if cal["mode"] == "segmented"
                   else "對齊籌碼K ≈ 本站算法 × k",
    })
    return cal


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
            r["ck_status"] = ck_status(r["date"], cal, r["ratio_pct"])
            n2 += 1
        for key in ("low_2025_04", "low_2024_08", "low_2024_07_08"):
            lo = bf.get(key)
            if isinstance(lo, dict) and lo.get("ratio_pct") is not None:
                lo["ratio_pct_ck"] = ck_value(lo["ratio_pct"], cal)
                lo["ck_status"] = ck_status(lo["date"], cal, lo["ratio_pct"])
        BACKFILL.write_text(json.dumps(bf, ensure_ascii=False, indent=1), encoding="utf-8")
    return n1, n2


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    existing = _load(OUT, {}) or {}
    if CM_DETAIL.exists():
        cal = build_cm(existing)
    elif existing.get("cm_calibration"):
        print("本機沒有 CM 估對帳明細（research/data/margin_reconcile/），沿用現有校準檔、不重建（避免蓋回舊值）")
        cal = existing
    else:
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
