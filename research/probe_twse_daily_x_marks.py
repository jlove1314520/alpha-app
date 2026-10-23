"""上市官方日檔「漲跌(+/-)」欄 X 標記 vs TWT49U 除權息表交叉核對（零請求）。

- 日檔：research/data/raw/v1_resume_day/twse/YYYYMMDD.json（MI_INDEX ALLBUT0999 原始回應，
  var1018_v1_reduction_events.py 抓的恢復買賣日；只有這批保留「漲跌(+/-)」欄原文）
  ＋ research/data/raw/twse_daily_2007h2/YYYYMMDD.json（fetch_twse_daily_2007h2.py 補抓 2007H2 其餘交易日）
- 除權息：research/data/raw/exright_2007_2014/twse_YYYY_H.json（2007H2～2012H2）
  ＋ research/data/raw/twse_twt49u/YYYY_H.json（2013～2014）
證交所「X」＝不比價，涵蓋除權息以外的情況（減資恢復買賣、新上市首日等），
所以「有 X 但 TWT49U 沒有」不等於 TWT49U 漏記，要另外分辨。
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
DAILY = HERE / "data" / "raw" / "v1_resume_day" / "twse"
DAILY_2007H2 = HERE / "data" / "raw" / "twse_daily_2007h2"  # fetch_twse_daily_2007h2.py 補抓的 2007H2 其餘交易日


def daily_files() -> list[Path]:
    """兩個原文日檔目錄合併，同一天以 v1_resume_day 為準。"""
    by_day = {f.stem: f for f in DAILY_2007H2.glob("*.json")}
    by_day.update({f.stem: f for f in DAILY.glob("*.json")})
    return [by_day[d] for d in sorted(by_day)]
EXR = [HERE / "data" / "raw" / "exright_2007_2014", HERE / "data" / "raw" / "twse_twt49u"]
OUT = HERE / "data" / "twse_daily_x_marks_vs_twt49u.json"
RESUME_CSV = HERE / "data" / "v1_reduction_events_2007_2014.csv"  # 停牌缺口（halt_to／resume_date）
OFFICIAL_DAILY = HERE / "data" / "v1_official_daily" / "twse"  # 缺口日官方日檔（只有部分日期）
CAL = HERE.parent / "data" / "trading_calendar.json"


def resume_keys() -> set:
    import csv
    out = set()
    try:
        with RESUME_CSV.open(encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                for col in ("resume_date", "halt_to"):
                    v = (r.get(col) or "").replace("-", "")
                    if v:
                        out.add((r["stock_id"].strip(), v))
    except Exception as e:  # noqa: BLE001 — 讀不到只是少一種分類
        print(f"⚠️ 讀不到 {RESUME_CSV.name}：{type(e).__name__}", flush=True)
    return out


def prev_day_traded(code: str, day: str, cache: dict):
    """回 True/False＝前一交易日官方日檔有/無該檔；None＝本機沒有那一天的日檔、判不了。
    前一交易日用兩個本機日檔目錄的日期聯集推（只在兩者連續時才可信，所以要求前一天檔案就在 DAILY 或 OFFICIAL_DAILY）。"""
    prev = cache.setdefault("_days", sorted({f.stem for f in OFFICIAL_DAILY.glob("*.json")} | {f.stem for f in daily_files()}))
    cands = [d for d in prev if d < day]
    if not cands:
        return None
    p = cands[-1]
    # 兩天之間隔超過 4 個日曆日（長假除外）就不保證是前一交易日
    from datetime import date as _d
    gap = (_d(int(day[:4]), int(day[4:6]), int(day[6:])) - _d(int(p[:4]), int(p[4:6]), int(p[6:]))).days
    if gap > 4:
        return None
    if p not in cache:
        f = OFFICIAL_DAILY / f"{p}.json"
        try:
            if f.exists():
                rows = json.loads(f.read_text(encoding="utf-8"))["rows"]
                # rows[代號]＝[開, 高, 低, 收, 量, 值]；收盤 None＝只有零股等成交、沒有收盤價
                cache[p] = {c for c, v in rows.items() if v and v[3] is not None}
            else:
                fp = DAILY / f"{p}.json"
                j = json.loads((fp if fp.exists() else DAILY_2007H2 / f"{p}.json").read_text(encoding="utf-8"))
                codes = set()
                for t in j.get("tables") or []:
                    fi = t.get("fields") or []
                    if "證券代號" in fi and "收盤價" in fi:
                        i, k = fi.index("證券代號"), fi.index("收盤價")
                        codes |= {str(r[i]).strip() for r in t.get("data") or [] if str(r[k]).strip() not in ("--", "")}
                cache[p] = codes
        except Exception as e:  # noqa: BLE001
            print(f"⚠️ 讀不到前一日 {p}：{type(e).__name__}", flush=True)
            return None
    return code in cache[p]


def roc_to_iso(s: str) -> str | None:
    m = re.match(r"\s*(\d+)年(\d+)月(\d+)日", str(s))
    if not m:
        return None
    return f"{int(m.group(1)) + 1911:04d}{int(m.group(2)):02d}{int(m.group(3)):02d}"


def twt49u_keys() -> tuple[set, dict]:
    keys, kind = set(), {}
    for d in EXR:
        for f in sorted(d.glob("*.json")):
            if d.name == "exright_2007_2014" and not f.name.startswith("twse_"):
                continue
            try:
                j = json.loads(f.read_text(encoding="utf-8"))
            except Exception as e:  # noqa: BLE001 — 單檔壞掉只略過
                print(f"⚠️ 讀不到 {f}：{type(e).__name__}", flush=True)
                continue
            fi = j.get("fields") or []
            if "資料日期" not in fi or "股票代號" not in fi:
                continue
            i_d, i_c = fi.index("資料日期"), fi.index("股票代號")
            i_k = fi.index("權/息") if "權/息" in fi else None
            for r in j.get("data") or []:
                iso = roc_to_iso(r[i_d])
                if iso:
                    k = (str(r[i_c]).strip(), iso)
                    keys.add(k)
                    kind[k] = r[i_k] if i_k is not None else None
    return keys, kind


def main() -> int:
    keys, kind = twt49u_keys()
    resumes = resume_keys()
    pcache: dict = {}
    per_day, x_only, hits = [], [], []
    tot = Counter()
    sym = Counter()
    for f in daily_files():
        day = f.stem
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"⚠️ 讀不到 {f.name}：{type(e).__name__}", flush=True)
            continue
        rows = None
        for t in j.get("tables") or []:
            fi = t.get("fields") or []
            if "漲跌(+/-)" in fi and "證券代號" in fi:
                rows = (fi.index("證券代號"), fi.index("漲跌(+/-)"), t.get("data") or [])
                break
        if rows is None:
            per_day.append({"date": day, "status": "無收盤行情表"})
            continue
        i_c, i_s, data = rows
        x_codes = set()
        for r in data:
            s = re.sub(r"<[^>]+>", "", str(r[i_s])).strip()
            sym[s or "(空白)"] += 1
            if s.upper() == "X":
                x_codes.add(str(r[i_c]).strip())
        tw = {c for (c, d) in keys if d == day}
        both = x_codes & tw
        tot["days"] += 1
        tot["x"] += len(x_codes)
        tot["twt49u"] += len(tw)
        tot["both"] += len(both)
        tot["twt49u_without_x"] += len(tw - x_codes)
        tot["x_without_twt49u"] += len(x_codes - tw)
        per_day.append({"date": day, "n_x": len(x_codes), "n_twt49u": len(tw), "n_both": len(both),
                        "twt49u_without_x": sorted(tw - x_codes), "x_without_twt49u": sorted(x_codes - tw)})
        for c in sorted(x_codes - tw):
            if (c, day) in resumes:
                why = "停牌後恢復買賣日（v1 停牌缺口表）"
            else:
                t = prev_day_traded(c, day, pcache)
                why = {True: "前一交易日有成交（原因未明：可能減資／新上市／其他不比價）",
                       False: "前一交易日無收盤價（無從比價）",
                       None: "本機無前一交易日日檔、判不了"}[t]
            x_only.append({"date": day, "code": c, "why": why})
        for c in sorted(both):
            hits.append({"date": day, "code": c, "twt49u_kind": kind.get((c, day))})
    h2007 = [p for p in per_day if p["date"][:6] >= "200707" and p["date"][:4] == "2007" and "n_x" in p]
    summary = {
        "daily_files": tot["days"], "twt49u_events_total_2007h2_2014": len(keys),
        "x_marks": tot["x"], "twt49u_on_these_days": tot["twt49u"], "both": tot["both"],
        "recall_twt49u_has_x_pct": round(100 * tot["both"] / tot["twt49u"], 2) if tot["twt49u"] else None,
        "x_without_twt49u": tot["x_without_twt49u"], "twt49u_without_x": tot["twt49u_without_x"],
        "x_without_twt49u_by_why": dict(Counter(x["why"] for x in x_only).most_common()),
        "symbols_seen": dict(sym.most_common()),
        "y2007h2": {"days": len(h2007), "x": sum(p["n_x"] for p in h2007),
                    "twt49u": sum(p["n_twt49u"] for p in h2007), "both": sum(p["n_both"] for p in h2007),
                    "twt49u_without_x": [(p["date"], c) for p in h2007 for c in p["twt49u_without_x"]],
                    "x_without_twt49u_by_why": dict(Counter(x["why"] for x in x_only
                                                            if "20070701" <= x["date"] <= "20071231").most_common()),
                    "x_without_twt49u_unexplained": [x for x in x_only if "20070701" <= x["date"] <= "20071231"
                                                     and x["why"].startswith("前一交易日有成交")]},
    }
    OUT.write_text(json.dumps({"generated_at": datetime.now().isoformat(timespec="seconds"),
                               "requests_sent": 0, "summary": summary, "per_day": per_day,
                               "x_without_twt49u": x_only}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
