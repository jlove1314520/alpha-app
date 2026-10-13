# -*- coding: utf-8 -*-
"""先.八十一-10（2026-10-13）：選股頁「主流題材（資金流入中）」改由 repo 內檔案計算，FinMind 只當補充。

原做法：對 FinMind 打 8 次 TaiwanStockPrice（產業指數代碼 Semiconductor／Electronic…），用各產業指數的
Trading_money 算「近 5 日均成交值 ÷ 近 20 日均成交值 − 1」。改成：data/price_history.json（每檔近 90 日
價量）＋ data/company_info.json（產業別），把同產業個股的每日成交值加總，用同一條公式算資金流入；
漲跌用同產業個股當日漲跌幅等權平均。比原本只看 8 個產業多涵蓋全部產業，而且產業名稱與選股榜一致
（點 chip 直接篩選），零外部請求。
擁擠度沿用原規則：從最新一天往回數「當日成交值 > 20 日均值」的連續天數（streak），這段期間等權
累積漲幅 ≥8% 且 streak≥3 標「已擁擠」——經驗規則，非統計檢定（與原 App 註解同）。
成分股 <5 檔的產業不列（樣本太小）。用法：python scripts/build_industry_flow.py
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "industry_flow.json"
MIN_MEMBERS = 5
TW = timezone(timedelta(hours=8))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    try:
        ph = json.loads((DATA / "price_history.json").read_text(encoding="utf-8")).get("prices") or {}
        comp = json.loads((DATA / "company_info.json").read_text(encoding="utf-8")).get("companies") or {}
    except (OSError, ValueError) as e:
        print(f"[warn] 讀不到 price_history／company_info（{type(e).__name__}），industry_flow.json 維持原狀")
        return 0
    money, rets, members = {}, {}, {}
    all_dates = set()
    for code, rows in ph.items():
        ind = (comp.get(code) or {}).get("industry")
        if not ind or not rows:
            continue
        members.setdefault(ind, set()).add(code)
        prev = None
        for r in rows:
            d, c, t = r.get("date"), r.get("close"), r.get("turnover")
            if not d:
                continue
            all_dates.add(d)
            if t is not None:
                money.setdefault(ind, {}).setdefault(d, 0.0)
                money[ind][d] += float(t)
            if prev and c and prev > 0:
                rets.setdefault(ind, {}).setdefault(d, []).append(c / prev - 1)
            prev = c if c else prev
    dates = sorted(all_dates)
    out_rows = []
    for ind, codes in members.items():
        if len(codes) < MIN_MEMBERS or ind not in money:
            continue
        ds = [d for d in dates if d in money[ind]]
        if len(ds) < 6:
            continue
        m = [money[ind][d] for d in ds]
        avg5 = sum(m[-5:]) / 5
        avg20 = sum(m[-20:]) / min(20, len(m))
        inflow = (avg5 / avg20 - 1) * 100 if avg20 > 0 else None
        streak = 0
        for v in reversed(m):
            if v > avg20:
                streak += 1
            else:
                break
        day_ret = {d: sum(v) / len(v) for d, v in (rets.get(ind) or {}).items() if v}
        cum = 1.0
        for d in ds[len(ds) - streak:] if streak else []:
            cum *= 1 + day_ret.get(d, 0.0)
        last = ds[-1]
        out_rows.append({"industry": ind, "members": len(codes), "date": last,
                         "inflow_pct": round(inflow, 2) if inflow is not None else None,
                         "pct": round(day_ret.get(last, 0.0) * 100, 2), "streak": streak,
                         "cum_gain_pct": round((cum - 1) * 100, 2),
                         "crowded": streak >= 3 and (cum - 1) * 100 >= 8})
    out_rows.sort(key=lambda r: -(r["inflow_pct"] if r["inflow_pct"] is not None else -1e9))
    doc = {"meta": {"generated_at": datetime.now(TW).isoformat(timespec="seconds"),
                    "data_date": dates[-1] if dates else None,
                    "source": "data/price_history.json 成交值（turnover）依 data/company_info.json 產業加總；scripts/build_industry_flow.py",
                    "formula": "資金流入％＝近5日平均成交值÷近20日平均成交值−1；漲跌＝同產業個股當日漲跌幅等權平均",
                    "min_members": MIN_MEMBERS},
           "industries": out_rows}
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    top = [f"{r['industry']} {r['inflow_pct']:+.1f}%" for r in out_rows[:5] if r["inflow_pct"] is not None]
    print(f"industry_flow：{len(out_rows)} 個產業，資料日 {doc['meta']['data_date']}；流入前五 {'、'.join(top)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
