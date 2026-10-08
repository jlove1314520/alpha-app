"""先.五十五 A2～A5：以總司令提供的 CMoney 估算維持率（經籌碼K顯示，本機 gitignore 檔）校準本站算法。

- 外部讀數只從本機 research/data/margin_reconcile/external_cm.json 讀；逐日比對明細只寫同目錄（gitignore）。
- 本程式輸出到 repo 的只有推導統計（k、誤差、分段、相關係數、判定），不含任何外部逐日數值。
- 本站原值：重用 backfill_margin_history 的 TWSE rwd MI_MARGN（間隔 ≥4 秒）＋同日官方收盤，分子分母同一回應同一天。

用法：python research/reconcile_cm_external.py
"""
from __future__ import annotations

import json
import statistics as st
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import backfill_margin_history as B  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
LOCAL = REPO / "research" / "data" / "margin_reconcile"
EXT = LOCAL / "external_cm.json"
DETAIL = LOCAL / "cm_reconcile_detail.json"        # 本機 gitignore：逐日明細（含外部值）
SUMMARY = LOCAL / "cm_reconcile_summary.json"      # 本機：推導統計（給 build_margin_calibration 讀）
DENOM_TOL_100M = 0.1                               # 原文：分母＝外部融資餘額 ±0.1 億
CRASH = ("2026-07-27", "2026-08-04")               # 原文：7/27～8/04 急跌段
SPAN_LIMIT = 0.01                                  # 原文判定門檻：全段 k 最大−最小 ≤0.01 → 單一 k
TIERS = [(None, 180.0), (180.0, 195.0), (195.0, None)]   # 原文示例分段（本站水位 %）


def _ours(day: str, ph: dict) -> dict | None:
    ds = day.replace("-", "")
    m = B.parse_margn(B._get(B.MARGN, {"date": ds, "selectType": "ALL"}, B.RAW / f"MI_MARGN_{ds}.json"))
    if m is None or m[0] != day:
        return None
    _, money, lots = m
    closes = B.closes_from_ph(ph, day)
    src = "price_history.json"
    cov = sum(v for c, v in lots.items() if c in closes) / (sum(lots.values()) or 1)
    if cov < B.COVER_MIN:
        closes = B.parse_mi_index(B._get(B.MI_INDEX, {"date": ds, "type": "ALLBUT0999"}, B.RAW / f"MI_INDEX_{ds}.json"))
        src = "TWSE MI_INDEX"
    rec = B.compute(day, money, lots, closes)
    rec["close_source"] = src
    return rec


def _stats(xs: list[float]) -> dict:
    if not xs:
        return {"n": 0}
    return {"n": len(xs), "median": round(st.median(xs), 5), "min": round(min(xs), 5), "max": round(max(xs), 5),
            "span": round(max(xs) - min(xs), 5), "stdev": round(st.stdev(xs), 5) if len(xs) > 1 else 0.0}


def _corr(a: list[float], b: list[float]) -> float | None:
    if len(a) < 3:
        return None
    ma, mb = st.mean(a), st.mean(b)
    sa = sum((x - ma) ** 2 for x in a) ** 0.5
    sb = sum((y - mb) ** 2 for y in b) ** 0.5
    if not sa or not sb:
        return None
    return round(sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb), 4)


def _ret20(ph: dict, day: str) -> float | None:
    """大盤代理：0050 近 20 個交易日漲跌幅（price_history）。"""
    rows = sorted((r for r in ph.get("0050", []) if r.get("close")), key=lambda r: r["date"])
    idx = next((i for i, r in enumerate(rows) if str(r["date"])[:10] == day), None)
    if idx is None or idx < 20:
        return None
    return rows[idx]["close"] / rows[idx - 20]["close"] - 1


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ext = json.loads(EXT.read_text(encoding="utf-8"))["points"]
    ph = json.loads((REPO / "data" / "price_history.json").read_text(encoding="utf-8")).get("prices") or {}
    detail, excluded, missing = [], [], []
    for day, bal_100m, ext_pct in ext:
        r = _ours(day, ph)
        if r is None:
            missing.append({"date": day, "reason": "MI_MARGN 查無同日資料"})
            continue
        if r.get("data_incomplete"):
            missing.append({"date": day, "reason": r.get("incomplete_reason")})
            continue
        ours_100m = r["margin_money"] / 1e8
        diff = ours_100m - bal_100m
        row = {"date": day, "ext_pct": ext_pct, "ext_bal_100m": bal_100m, "ours_pct": r["ratio_pct"],
               "ours_bal_100m": round(ours_100m, 2), "denom_diff_100m": round(diff, 2), "close_source": r["close_source"],
               "lots_coverage": r["lots_coverage"], "ret20_0050": _ret20(ph, day)}
        if abs(diff) > DENOM_TOL_100M:
            row["excluded"] = True
            excluded.append({"date": day, "denom_diff_direction": "本站較高" if diff > 0 else "本站較低",
                             "denom_diff_100m_abs": round(abs(diff), 2)})
        else:
            row["k"] = ext_pct / r["ratio_pct"]
        detail.append(row)
        print(day, "ours", r["ratio_pct"], "denom_diff", round(diff, 2), "k", round(row.get("k", float("nan")), 5), flush=True)
    LOCAL.mkdir(parents=True, exist_ok=True)
    DETAIL.write_text(json.dumps({"generated_at": datetime.now(B.TW).isoformat(timespec="seconds"), "rows": detail,
                                  "excluded": excluded, "missing": missing}, ensure_ascii=False, indent=1), encoding="utf-8")
    used = [d for d in detail if "k" in d]
    ks = [d["k"] for d in used]
    crash = [d["k"] for d in used if CRASH[0] <= d["date"] <= CRASH[1]]
    other = [d["k"] for d in used if not (CRASH[0] <= d["date"] <= CRASH[1])]
    lvl = [d["ours_pct"] for d in used]
    r20 = [(d["k"], d["ret20_0050"]) for d in used if d["ret20_0050"] is not None]
    allk = _stats(ks)
    single = allk["n"] > 0 and allk["span"] <= SPAN_LIMIT
    tiers = []
    for lo, hi in TIERS:
        xs = [d["k"] for d in used if (lo is None or d["ours_pct"] >= lo) and (hi is None or d["ours_pct"] < hi)]
        tiers.append({"lo": lo, "hi": hi, **_stats(xs)})
    summary = {
        "generated_at": datetime.now(B.TW).isoformat(timespec="seconds"),
        "source": "CMoney 估算（經籌碼K顯示）；讀數由總司令提供，只存本機，不入 repo",
        "n_provided": len(ext), "n_used": len(used), "excluded": excluded, "missing": missing,
        "k_all": allk, "k_crash_0727_0804": _stats(crash), "k_other": _stats(other),
        "corr_k_vs_ours_level": _corr(ks, lvl),
        "corr_k_vs_ret20_0050": _corr([a for a, _ in r20], [b for _, b in r20]), "n_ret20": len(r20),
        "ours_level_range": [round(min(lvl), 2), round(max(lvl), 2)] if lvl else None,
        "decision_rule": f"全段 k 最大−最小 ≤{SPAN_LIMIT} → 單一 k（中位數）；否則依本站水位分段 {TIERS} 各取中位數（先.五十五 A4，事前固定）",
        "decision": "single" if single else "tiered", "tiers": tiers,
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("n_used", "k_all", "k_crash_0727_0804", "k_other", "corr_k_vs_ours_level",
                                               "corr_k_vs_ret20_0050", "decision", "tiers", "excluded", "missing")},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
