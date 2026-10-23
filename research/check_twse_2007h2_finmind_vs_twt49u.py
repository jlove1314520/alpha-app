"""上市 2007H2：FinMind 股利金額推算參考價 vs TWT49U 官方參考價（零請求）。

用途：估 build_tpex_exright_2007h2_ref.py（上櫃只能用 FinMind 金額推）那批推算值的可信度。
同一套公式：(除權息前收盤 − 現金股利 ＋ 認購率×認購價) ÷ (1 ＋ 配股元數/10 ＋ 認購率)，
前收盤直接用 TWT49U 的「除權息前收盤價」，所以差距只反映 FinMind 金額／日期跟官方不一致。
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_tpex_exright_2007h2_ref import _num, dividend_rows  # noqa: E402

SRC = HERE / "data" / "raw" / "exright_2007_2014" / "twse_2007_2.json"
OUT = HERE / "data" / "twse_2007h2_finmind_vs_twt49u.json"


def roc_iso(s: str) -> str:
    m = re.match(r"\s*(\d+)年(\d+)月(\d+)日", s)
    return f"{int(m.group(1)) + 1911:04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def main() -> int:
    j = json.loads(SRC.read_text(encoding="utf-8"))
    fi = j["fields"]
    ix = {k: fi.index(k) for k in ("資料日期", "股票代號", "股票名稱", "除權息前收盤價", "除權息參考價", "權值", "息值", "權/息")}
    rows, unmatched = [], []
    cache: dict = {}
    for r in j["data"]:
        code, d = str(r[ix["股票代號"]]).strip(), roc_iso(r[ix["資料日期"]])
        prev, ref_off = _num(str(r[ix["除權息前收盤價"]]).replace(",", "")), _num(str(r[ix["除權息參考價"]]).replace(",", ""))
        base = {"date": d, "code": code, "name": r[ix["股票名稱"]], "kind": r[ix["權/息"]],
                "prev_close": prev, "ref_official": ref_off,
                "official_stock_value": _num(r[ix["權值"]]), "official_cash_value": _num(r[ix["息值"]])}
        if code not in cache:
            cache[code] = dividend_rows(code)
        dv = cache[code]
        if dv is None:
            unmatched.append({**base, "reason": "無 FinMind 股利快取"})
            continue
        cash = stock = sub_rate = sub_px = 0.0
        hit = False
        for x in dv.itertuples():
            if str(x.CashExDividendTradingDate or "")[:10] == d:
                cash += _num(x.CashEarningsDistribution) + _num(x.CashStatutorySurplus)
                hit = True
            if str(x.StockExDividendTradingDate or "")[:10] == d:
                stock += _num(x.StockEarningsDistribution) + _num(x.StockStatutorySurplus)
                sub_rate += _num(x.CashIncreaseSubscriptionRate)
                sub_px = max(sub_px, _num(x.CashIncreaseSubscriptionpRrice))
                hit = True
        if not hit:
            unmatched.append({**base, "reason": "FinMind 該日無紀錄" if not dv.empty else "FinMind 整段零筆股利"})
            continue
        if sub_rate > 1:  # FinMind 認購率在這批是百分比（每百股認購股數），÷100 才對得上官方參考價
            sub_rate = sub_rate / 100.0
        if not prev or not ref_off:
            unmatched.append({**base, "reason": "官方前收或參考價缺"})
            continue
        ref_fm = (prev - cash + sub_rate * sub_px) / (1 + stock / 10.0 + sub_rate)
        rows.append({**base, "finmind_cash": round(cash, 6), "finmind_stock_yuan": round(stock, 6),
                     "finmind_cash_increase_rate": round(sub_rate, 6), "ref_finmind": round(ref_fm, 4),
                     "diff_pct": round((ref_fm / ref_off - 1) * 100, 3),
                     "cash_matches_official": abs(cash - base["official_cash_value"]) < 0.005})
    diffs = [abs(x["diff_pct"]) for x in rows]
    reasons: dict = {}
    for u in unmatched:
        reasons[u["reason"]] = reasons.get(u["reason"], 0) + 1
    summary = {"n_twt49u": len(j["data"]), "n_matched": len(rows), "n_unmatched": len(unmatched),
               "unmatched_by_reason": reasons,
               "within_0_1pct": sum(x < 0.1 for x in diffs), "within_0_5pct": sum(x < 0.5 for x in diffs),
               "within_1pct": sum(x < 1 for x in diffs), "over_1pct": sum(x >= 1 for x in diffs),
               "max_abs_pct": max(diffs) if diffs else None,
               "cash_amount_mismatch": sum(not x["cash_matches_official"] for x in rows)}
    OUT.write_text(json.dumps({"generated_at": datetime.now().isoformat(timespec="seconds"), "requests_sent": 0,
                               "summary": summary, "worst": sorted(rows, key=lambda x: -abs(x["diff_pct"]))[:30],
                               "unmatched": unmatched}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
