# -*- coding: utf-8 -*-
"""從 data/market_us.json 的 git 歷史回填 data/us_index_close_history.json（先.一三八-5，Cowork 收件匣 027 已定案）。

零外部請求：只讀本機 git 歷史（git log／git show）。
- 日期以資料自帶的 as_of（收盤日，美東）為準，不用 commit 時間。
- 盤中值不收：有 intraday 欄位照欄位；舊版沒有 intraday 欄位（先.一〇三-12 之前）時，
  用資料自帶 fetched_at（沒有才用 commit 時間）換算美東，as_of＝當天美東日期且早於 16:00 → 視為盤中，略過。
- 只有盤中版本的日子（沒有收盤版）用 sparkline 錨定補：取某個收盤版的 20 點 sparkline，
  兩端都對得上已知收盤日的收盤值、且中間點數＝兩日之間美股交易日數，才把中間點標上日期，
  列加 method=sparkline_anchor；對不上就不補、照實列出缺口。
- 每日（每個 as_of）取時間上最後一版；重複日去重。回填列標 source=git_backfill。
- 已有的 source=yfinance（每日管線）列不被回填覆蓋。

用法：python scripts/backfill_us_index_close_history.py [--dry-run]
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".github" / "scripts"))
import us_index_close_history as H  # noqa: E402

ET = ZoneInfo("America/New_York")
SRC = "data/market_us.json"


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, check=True,
                          encoding="utf-8", errors="replace").stdout


def collect() -> tuple[dict, dict]:
    """回傳 ({(ticker, date): (commit_time, close, name)}, 統計)。"""
    log = _git("log", "--format=%H %cI", "--", SRC).strip().splitlines()
    best: dict = {}
    stats = {"commits": len(log), "bad_json": 0, "intraday_skipped": 0, "rows_seen": 0}
    for line in log:
        sha, ts = line.split(" ", 1)
        ct = datetime.fromisoformat(ts)
        try:
            d = json.loads(_git("show", f"{sha}:{SRC}"))
        except Exception:
            stats["bad_json"] += 1
            continue
        fa = d.get("fetched_at")
        ct_et = (datetime.fromisoformat(fa) if fa else ct).astimezone(ET)
        for ticker, v in (d.get("indices") or {}).items():
            if not isinstance(v, dict) or not v.get("as_of") or v.get("close") is None:
                continue
            asof = v["as_of"]
            if "intraday" in v:
                intraday = v["intraday"] is True
            else:
                intraday = asof == ct_et.strftime("%Y-%m-%d") and ct_et.hour < 16
            if intraday:
                stats["intraday_skipped"] += 1
                continue
            stats["rows_seen"] += 1
            key = (ticker, asof)
            if key not in best or ct > best[key][0]:
                best[key] = (ct, v["close"], v.get("name"), v.get("sparkline") or [])
    return best, stats


# 美股休市日（只列回填區間會碰到的；NYSE 官方 2026 休市表：Labor Day 09-07、感恩節 11-26）
US_HOLIDAYS = {"2026-09-07", "2026-11-26"}


def _trading_days_between(a: str, b: str) -> list[str]:
    from datetime import date, timedelta
    d0, d1 = date.fromisoformat(a), date.fromisoformat(b)
    out, d = [], d0 + timedelta(days=1)
    while d < d1:
        if d.weekday() < 5 and d.isoformat() not in US_HOLIDAYS:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def sparkline_fill(best: dict) -> dict:
    """回傳 {(ticker, date): close}，只補 best 裡沒有的日子。"""
    fills: dict = {}
    for ticker in sorted({t for t, _ in best}):
        known = {d: c for (t, d), (_, c, _, _) in best.items() if t == ticker}
        dates = sorted(known)
        for i in range(len(dates) - 1):
            a, b = dates[i], dates[i + 1]
            gap = _trading_days_between(a, b)
            if not gap:
                continue
            # 找任何一個 as_of >= b 的收盤版 sparkline，兩端錨點值都吻合
            for (t, d), (_, c, _, spark) in sorted(best.items()):
                if t != ticker or d < b or len(spark) < len(gap) + 2:
                    continue
                vals = [round(float(x), 2) for x in spark]
                # sparkline 最後一點＝d 的收盤；往回數到 b
                later = [x for x in dates if b <= x <= d]
                jb = len(vals) - 1 - (len(later) - 1)  # b 在 sparkline 的位置（假設 b..d 之間無缺口）
                if any(_trading_days_between(later[k], later[k + 1]) for k in range(len(later) - 1)):
                    continue  # b..d 之間本身有缺口，位置推不準，換一個版本
                ja = jb - len(gap) - 1
                if ja < 0 or vals[jb] != round(known[b], 2) or vals[ja] != round(known[a], 2):
                    continue
                for k, gd in enumerate(gap):
                    fills[(ticker, gd)] = vals[ja + 1 + k]
                break
    return fills


def main() -> int:
    dry = "--dry-run" in sys.argv
    best, stats = collect()
    hist = H.load()
    added = 0
    fills = sparkline_fill(best)
    for (ticker, date), (ct, close, name, _) in sorted(best.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        existing = {r["date"]: r for r in hist.get("series", {}).get(ticker, [])}
        if date in existing and existing[date].get("source") != "git_backfill":
            continue  # 每日管線寫的不覆蓋
        if H.merge(hist, ticker, name, date, close, "git_backfill"):
            for r in hist["series"][ticker]:
                if r["date"] == date:
                    r["git_commit_at"] = ct.isoformat()  # 取用的那一版 commit 時間（非抓取時間）
            added += 1
    for (ticker, date), close in sorted(fills.items()):
        existing = {r["date"]: r for r in hist.get("series", {}).get(ticker, [])}
        if date in existing and existing[date].get("source") != "git_backfill":
            continue
        if H.merge(hist, ticker, None, date, close, "git_backfill"):
            for r in hist["series"][ticker]:
                if r["date"] == date:
                    r["method"] = "sparkline_anchor"
            added += 1
    fill_dates = sorted({d for (_, d) in fills})
    print(f"sparkline 錨定補 {len(fills)} 筆：{fill_dates}")
    all_dates = sorted({d for (_, d) in best} | set(fill_dates))
    if all_dates:
        miss = [x for x in _trading_days_between(all_dates[0], all_dates[-1]) if x not in all_dates]
        print(f"區間內仍缺的美股交易日：{miss or '無'}")
    dates = sorted({d for (_, d) in best})
    print(f"git 版本 {stats['commits']} 個（壞檔 {stats['bad_json']}），收盤列 {stats['rows_seen']}、"
          f"略過盤中 {stats['intraday_skipped']}；去重後 {len(best)} 筆、{len(dates)} 個收盤日"
          f"（{dates[0] if dates else '-'}～{dates[-1] if dates else '-'}）；寫入變動 {added} 列")
    for t, rows in sorted(hist.get("series", {}).items()):
        print(f"  {t}: {len(rows)} 列")
    if not dry and added:
        H.save(hist)
        print(f"已寫 {H.HISTORY_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
