"""先.一三五-1s 候選 N8 前置：SOX 日線與台股半導體業名單的本機可得性（零請求）。

只看欄位名、日期與檔數，不讀 SOX 漲跌數值、不數事件日、不算報酬、不登記試驗。
輸出：research/data/cand_n8_data_probe.json
"""
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "research/data/cand_n8_data_probe.json"


def load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def sox_probe() -> dict:
    mu = load("data/market_us.json")
    sox = mu.get("indices", {}).get("^SOX", {})
    res = {
        "market_us_json": {"top_keys": list(mu.keys()), "sox_fields": sorted(sox.keys()),
                           "sox_as_of": sox.get("as_of"),
                           "sparkline_points": len(sox.get("sparkline") or []),
                           "sparkline_has_dates": False},
    }
    # 逐日累積：看 repo 追蹤檔裡有沒有帶日期的 SOX 序列
    g = subprocess.run(["git", "grep", "-l", "SOX", "--", "data/", "research/*.json", "research/*.jsonl"],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=60)
    res["tracked_files_mentioning_SOX"] = sorted(set(g.stdout.split()))
    # 本機 research/data（不進 repo）裡檔名含 sox 的
    rd = ROOT / "research/data"
    res["local_research_data_sox_files"] = sorted(p.name for p in rd.glob("*") if "sox" in p.name.lower())
    # market_us.json 的 git 歷史筆數＝雲端每班覆寫一次（可從 git log 回推每日收盤，但不是累積檔）
    lg = subprocess.run(["git", "log", "--since=2026-01-01", "--format=%cs", "--", "data/market_us.json"],
                        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=120)
    days = sorted(set(lg.stdout.split()))
    res["market_us_json_git_history"] = {"commits": len(lg.stdout.split()), "distinct_days": len(days),
                                         "first": days[0] if days else None, "last": days[-1] if days else None}
    return res


def semi_probe() -> dict:
    ci = load("data/company_info.json")["companies"]
    semi = sorted(c for c, v in ci.items() if isinstance(v, dict) and v.get("industry") == "半導體業")
    active = set(load("data/listed_universe.json")["active"])
    by_src = Counter()
    missing = 0
    for code in semi:
        p = ROOT / "data/by_code" / f"{code}.json"
        if not p.exists():
            missing += 1
            continue
        comp = json.loads(p.read_text(encoding="utf-8")).get("company", {})
        by_src[comp.get("industry_source") or "未標"] += 1
    return {"source_file": "data/company_info.json（companies[代號].industry）＋ data/by_code/*.json company.industry_source",
            "n_semi_company_info": len(semi), "n_semi_active": len(semi & active if isinstance(semi, set) else set(semi) & active),
            "industry_source_counts": dict(by_src), "by_code_missing": missing}


def open_price_probe() -> dict:
    meta = load("data/price_history/_meta.json")
    b = load("data/price_history/b2.json")["prices"]
    code, rows = next((c, r) for c, r in b.items() if c == "2330") if "2330" in b else next(iter(b.items()))
    dates = [r["date"] for r in rows]
    return {"files": sorted(p.name for p in (ROOT / "data/price_history").glob("*.json")),
            "row_fields": sorted(rows[-1].keys()), "has_open": "open" in rows[-1],
            "sample_code": code, "sample_first": dates[0], "sample_last": dates[-1], "sample_rows": len(dates),
            "meta_keys": list(meta.keys())[:10]}


def main() -> None:
    out = {"item": "先.一三五-1s",
           "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
           "network_requests": 0}
    for name, fn in (("sox", sox_probe), ("semiconductor_list", semi_probe), ("tw_open_price", open_price_probe)):
        try:
            out[name] = fn()
        except Exception as e:  # 單一子項失敗只降級
            print(f"警告：{name} 探測失敗：{type(e).__name__}: {e}")
            out[name] = {"error": f"{type(e).__name__}: {e}"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False)[:2500])


if __name__ == "__main__":
    main()
