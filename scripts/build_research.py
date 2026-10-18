# -*- coding: utf-8 -*-
"""研究室.一（2026-10-14，Cowork 代擬、總司令授權）：全市場研究層 data/research.json＋data/research_radar.json。

定位（務必讀）：
- 這是「研究紀錄／變化偵測」，不是評分因子。凍結.二仍有效：本檔任何欄位不得進 scores*.json、
  不得當選股權重；change_tags／change_score 只是「這檔最近哪裡變了」的描述性排序，未經回測。
- 零外部請求：只讀 repo 內既有檔（price_history／fundamentals／stock_detail／institutional_history／
  events／holders／company_info／listed_universe）＋ research/lab/（A 級深度研究的人工設定）。
- 自身失敗只降級成警告（CLAUDE.md 十二）：單檔出錯記進 meta.errors，整支一律 exit 0。

三層：
  L1 全市場（每檔）：營收、毛利、估值、價量、法人、大戶、事件 → 指標＋change_tags
  L2 變化雷達：依規則挑出「最近變化最大」的名單（research_radar.json），附產業營收熱度
  L3 深度（research/lab/config/<代號>.json）：論點、情境 EPS、人工指標、管理層說法 PIT 紀錄

輸出：
  data/research.json        {"meta":…, "stocks": {代號: {...}}}（build_by_code 會切進每檔小檔）
  data/research_radar.json  {"meta":…, "lists": {...}, "industry_heat": [...], "deep": [...]}
用法：python scripts/build_research.py [--asof YYYY-MM-DD]
"""
from __future__ import annotations

import datetime as dt
import json
import statistics
import sys
import traceback
from pathlib import Path

import os
ROOT = Path(os.environ.get("ALPHA_ROOT") or Path(__file__).resolve().parent.parent)
DATA = ROOT / "data"
import os
LAB = Path(os.environ.get("RESEARCH_LAB", ROOT / "research" / "lab"))
OUT = Path(os.environ.get("RESEARCH_OUT", DATA))
sys.path.insert(0, str(ROOT / "scripts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCHEMA = "research-v2"
TZ = dt.timezone(dt.timedelta(hours=8))
DISCLAIMER = "研究紀錄與變化偵測，非投資建議；變化排序未經回測，不是買賣訊號。"
LIQ_MIN_TURNOVER = 30_000_000  # 雷達名單流動性門檻：近 20 日平均成交值 ≥ 3,000 萬
NON_STOCK_INDUSTRY = ("ETF", "ETN", "基金", "受益", "存託憑證", "Index", "所有證券", "指數")
RULE_TEXT = {
    "營收加速": "近3月營收年增 ≥20% 且比前3月年增多 ≥10 個百分點",
    "營收轉正": "近3月營收年增由 ≤0 轉 >0",
    "營收轉弱": "近3月營收年增比前3月少 ≥20 個百分點且 <10%",
    "營收創新高": "最新月營收為近 24 個月以上最高",
    "毛利率跳升": "最新一季毛利率比上一季高 ≥3 個百分點",
    "毛利率轉差": "最新一季毛利率比上一季低 ≥3 個百分點",
    "法說將至": "未來 14 天內（含今天）有法說會舉行（日期取重大訊息寫明的舉行日，沒寫舉行日的公告不算）",
    "量增創 60 日新高": "收盤為 60 日新高且近5日均量 ≥1.5×20日均量",
    "創高量縮": "收盤為 60 日新高但近5日均量 <0.8×20日均量",
    "量增跌破 60 日均線": "近3日由 60 日均線上跌破 MA60 且當日量 ≥1.5×20日均量",
    "投信連買": "投信連續 ≥5 個交易日買超",
    "法人背離": "近20日股價 ≥+10% 但外資賣超，或 ≤−10% 但外資買超",
    "大戶增持": "千張大戶持股比例單週增 ≥0.5 個百分點且連 ≥2 週（集保缺週、兩筆相隔超過 9 天時不算單週、不打標籤）",
    "重大訊息": "近7日有重大訂單／併購／處分資產／財務／訴訟類重大訊息",
}
FUND_TAGS = {"營收加速", "營收轉正", "營收轉弱", "營收創新高", "毛利率跳升", "毛利率轉差"}
NEG_TAGS = {"營收轉弱", "毛利率轉差", "量增跌破 60 日均線", "創高量縮"}


def load(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"::warning::讀不到 {p.name}：{e}")
        return default


def r4(x):
    return None if x is None else round(x, 4)


# ---------------------------------------------------------------- L1 指標
REV_BACKFILL, FIN_BACKFILL = {}, {}  # 研究室.二／三 的回補檔（App 顯示用，main() 載入）


def merged_revenue(f, code=None):
    """回補檔 ∪ fundamentals.revenue_history_scoring ∪ month_revenue；同月以後者為準（官方每日管線最新）。"""
    m = {}
    for src in (REV_BACKFILL.get(code) or [], (f or {}).get("revenue_history_scoring") or [], (f or {}).get("month_revenue") or []):
        for r in src:
            if r.get("revenue") is not None:
                m[(int(r["year"]), int(r["month"]))] = r
    return [m[k] for k in sorted(m)]


def _shift(y, mth, k):
    t = y * 12 + (mth - 1) - k
    return t // 12, t % 12 + 1


def revenue_metrics(h):
    """h：merged_revenue()。視窗一律依日曆月份取，缺任何一個月就不算（附 reason），不拿不連續的月份硬湊。"""
    out = {"rev_last_month": None, "rev_last": None, "rev3_yoy": None, "rev3_yoy_prev": None, "rev3_qoq": None,
           "rev_high_months": None, "rev_months_available": len(h)}
    if not h:
        out["reason"] = "無月營收"
        return out
    key = {(r["year"], r["month"]): r for r in h}
    last = h[-1]
    ly0, lm0 = last["year"], last["month"]
    out["rev_last_month"] = f"{ly0}-{lm0:02d}"
    out["rev_last"] = last["revenue"]

    def win(k0):
        ms = [_shift(ly0, lm0, k) for k in (k0 + 2, k0 + 1, k0)]
        if not all(m in key for m in ms):
            return None, None
        cur = sum(key[m]["revenue"] for m in ms)
        ly = []
        for (y, mth) in ms:  # 去年同月：原始數字優先，缺就用官方 yoy 反推（營收 ÷（1＋yoy））
            r0 = key.get((y - 1, mth))
            v = r0["revenue"] if r0 else None
            r = key[(y, mth)]
            if not v and r.get("yoy") is not None and r["yoy"] > -1:
                v = r["revenue"] / (1 + r["yoy"])
            ly.append(v)
        return cur, (cur / sum(ly) - 1 if all(ly) else None)

    cur, out["rev3_yoy"] = win(0)
    prev, out["rev3_yoy_prev"] = win(3)
    if cur and prev:
        out["rev3_qoq"] = cur / prev - 1
    span = [_shift(ly0, lm0, k) for k in range(24)]
    if sum(m in key for m in span) >= 20:  # 近 24 個月至少有 20 個月才判「創新高」
        out["rev_high_months"] = 24 if last["revenue"] >= max(key[m]["revenue"] for m in span if m in key) else 0
    for k in ("rev3_yoy", "rev3_yoy_prev", "rev3_qoq"):
        out[k] = r4(out[k])
    if out["rev3_yoy"] is None:
        out["reason"] = "近3月或去年同期月營收不齊"
    elif out["rev3_qoq"] is None:
        out["reason"] = "前3月月營收不齊，無法算季增"
    return out


def expected_latest_quarter(asof: dt.date):
    """依法定期限推算「應已公布」的最新季：Q1 5/15、Q2 8/14、Q3 11/14、Q4 隔年 3/31。"""
    y = asof.year
    if asof >= dt.date(y, 11, 14):
        return (y, 3)
    if asof >= dt.date(y, 8, 14):
        return (y, 2)
    if asof >= dt.date(y, 5, 15):
        return (y, 1)
    if asof >= dt.date(y, 3, 31):
        return (y - 1, 4)
    return (y - 1, 3)


def quarter_metrics(fin, asof, backfill=None):
    m = {(q["year"], q["quarter"]): q for q in (backfill or [])}
    m.update({(q["year"], q["quarter"]): q for q in ((fin or {}).get("quarters") or [])})  # 官方管線優先
    qs = [m[k] for k in sorted(m)]
    out = {"q_last": None, "gm": None, "gm_qoq_pp": None, "gm_yoy_pp": None, "opm": None, "eps_ttm": None,
           "q_stale": None, "shares_k": (fin or {}).get("shares_outstanding_approx")}
    if not qs:
        out["reason"] = "無季報（上櫃財報端點未接或新上市）"
        out["q_stale"] = True
        return out
    q = qs[-1]
    out["q_last"] = f"{q['year']}Q{q['quarter']}"
    out["gm"], out["opm"] = q.get("gross_margin_pct"), q.get("op_margin_pct")
    exp = expected_latest_quarter(asof)
    out["q_stale"] = (q["year"], q["quarter"]) < exp
    if out["q_stale"]:
        out["reason"] = f"季報停在 {out['q_last']}，應已有 {exp[0]}Q{exp[1]}"
    if len(qs) >= 2 and q.get("gross_margin_pct") is not None and qs[-2].get("gross_margin_pct") is not None:
        out["gm_qoq_pp"] = round(q["gross_margin_pct"] - qs[-2]["gross_margin_pct"], 2)
    ly = next((x for x in qs if x["year"] == q["year"] - 1 and x["quarter"] == q["quarter"]), None)
    if ly and ly.get("gross_margin_pct") is not None and q.get("gross_margin_pct") is not None:
        out["gm_yoy_pp"] = round(q["gross_margin_pct"] - ly["gross_margin_pct"], 2)
    if len(qs) >= 4 and all(x.get("eps") is not None for x in qs[-4:]):
        out["eps_ttm"] = round(sum(x["eps"] for x in qs[-4:]), 2)
    return out


def price_metrics(rows):
    rows = [r for r in (rows or []) if r.get("close")]
    out = {"close": None, "price_date": None, "ret20": None, "ret60": None, "ma20": None, "ma60": None,
           "hi60": None, "lo60": None, "vol5_20": None, "turnover20": None, "flags": []}
    if len(rows) < 25:
        out["reason"] = f"價量資料只有 {len(rows)} 日"
        if rows:
            out["close"], out["price_date"] = rows[-1]["close"], rows[-1]["date"]
        return out
    c = [r["close"] for r in rows]
    ac = [r.get("adj_close") or r["close"] for r in rows]
    v = [r.get("volume") or 0 for r in rows]
    t = [r.get("turnover") or 0 for r in rows]
    out["close"], out["price_date"] = c[-1], rows[-1]["date"]
    out["ret20"] = r4(ac[-1] / ac[-21] - 1)
    if len(ac) >= 61:
        out["ret60"] = r4(ac[-1] / ac[-61] - 1)
    out["ma20"] = round(sum(c[-20:]) / 20, 2)
    w60 = c[-60:]
    out["ma60"] = round(sum(w60) / len(w60), 2) if len(w60) >= 60 else None
    out["hi60"], out["lo60"] = max(w60), min(w60)
    v20 = sum(v[-20:]) / 20
    out["vol5_20"] = round((sum(v[-5:]) / 5) / v20, 2) if v20 else None
    out["turnover20"] = round(sum(t[-20:]) / 20)
    # 近 10 日逐日標記（事實，不含推測）
    for i in range(max(21, len(rows) - 10), len(rows)):
        base = sum(v[i - 20:i]) / 20
        if not base or not c[i - 1]:
            continue
        ret, vr = c[i] / c[i - 1] - 1, v[i] / base
        tags = []
        if ret >= 0.05 and vr >= 1.5: tags.append("帶量大漲")
        if ret >= 0.05 and vr < 1.0: tags.append("大漲量縮")
        if ret <= -0.05 and vr >= 1.5: tags.append("帶量大跌")
        if vr >= 3: tags.append("爆量>3倍")
        if tags:
            out["flags"].append({"date": rows[i]["date"], "close": c[i], "ret": r4(ret), "vol_ratio": round(vr, 2), "tags": tags})
    return out


def inst_metrics(series, dates):
    out = {"foreign10": None, "trust10": None, "foreign20": None, "trust_streak": 0, "inst_days": 0}
    if not series:
        out["reason"] = "無法人歷史"
        return out
    ds = [d for d in dates if d in series]
    out["inst_days"] = len(ds)
    if len(ds) < 10:
        out["reason"] = f"法人歷史只有 {len(ds)} 日"
    last10, last20 = ds[-10:], ds[-20:]
    out["foreign_missing_days"] = sum(1 for d in ds[-20:] if not series[d] or series[d][0] is None)
    if out["foreign_missing_days"]:
        out["reason"] = f"近20日有 {out['foreign_missing_days']} 日外資欄位缺值（上櫃外資資料缺漏，修復中）"

    def g(d, i):
        v = series[d][i] if len(series[d]) > i else None
        return 0 if v is None else v
    out["foreign10"] = round(sum(g(d, 0) for d in last10), 1)
    out["trust10"] = round(sum(g(d, 1) for d in last10), 1)
    out["foreign20"] = round(sum(g(d, 0) for d in last20), 1)
    for d in reversed(ds):
        if g(d, 1) > 0:
            out["trust_streak"] += 1
        else:
            break
    return out


def event_metrics(evs, asof):
    out = {"next_call": None, "recent_major": [], "events_30d": 0}
    for e in evs:
        try:
            d = dt.date.fromisoformat(e["date"][:10])
        except Exception:  # noqa: BLE001
            continue
        delta = (d - asof).days
        if -30 <= delta <= 0 and e.get("type") not in ("月營收",):
            out["events_30d"] += 1
        # 先.一〇三-4：法說將至看「法說舉行日」call_date（重大訊息說明欄／主旨解析），不看公告日；抓不到舉行日的不算
        cd = e.get("call_date") if e.get("type") == "法說會" else None
        if cd:
            try:
                cdelta = (dt.date.fromisoformat(cd[:10]) - asof).days
            except Exception:  # noqa: BLE001
                cdelta = None
            # delta<=0：公告要在 asof 當天或以前才看得到（--asof 回放時不偷看未來公告）
            if cdelta is not None and delta <= 0 and 0 <= cdelta <= 14 and (out["next_call"] is None or cd < out["next_call"]["date"]):
                out["next_call"] = {"date": cd[:10], "announced": e["date"][:10], "title": e.get("title", "")[:80], "url": e.get("url")}
        if e.get("type") in ("重大訂單", "併購", "處分資產", "財務", "訴訟") and -7 <= delta <= 0:
            out["recent_major"].append({"date": e["date"][:10], "type": e["type"], "title": e.get("title", "")[:80], "url": e.get("url")})
    return out


# 先.一〇三-14（2026-10-16）：--asof 回放時真正把資料截到該日（原本只有季報新鮮度與事件看 asof，
# 價量／月營收／季報／法人／集保／本益比都用到最新，回放會偷看未來）。截法一律保守：寧可少用一筆，不偷看。
def cut_prices(rows, asof):
    a = asof.isoformat()
    return [r for r in (rows or []) if str(r.get("date", ""))[:10] <= a]


def cut_revenue(h, asof):
    """月營收依法要在次月 10 日前公告；asof 當天還沒到公告期限的月份一律不用（保守，不看實際公告日）。"""
    out = []
    for r in h or []:
        y, m = int(r["year"]), int(r["month"])
        ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
        if dt.date(ny, nm, 10) <= asof:
            out.append(r)
    return out


def cut_quarters(fin, backfill, asof):
    """季報只留到 asof 當天已過法定公告期限的那一季（expected_latest_quarter），提早公告的也不用（保守）。"""
    exp = expected_latest_quarter(asof)
    ok = lambda q: (q["year"], q["quarter"]) <= exp  # noqa: E731
    fin2 = dict(fin or {})
    fin2["quarters"] = [q for q in ((fin or {}).get("quarters") or []) if ok(q)]
    return fin2, [q for q in (backfill or []) if ok(q)]


def holder_metrics(hd, asof):
    """集保：只用 asof 當天以前的週別；兩筆相隔超過 9 天（中間缺週）時變化不是「單週」，week_change_pct 給 None 並寫 gap_days。"""
    if not hd:
        return None
    a = asof.strftime("%Y%m%d")
    hist = sorted((h for h in (hd.get("history") or []) if str(h.get("date", "")) <= a and h.get("big_holder_ratio") is not None),
                  key=lambda h: h["date"])
    if not hist:
        return None
    d = lambda x: dt.date(int(x[:4]), int(x[4:6]), int(x[6:8]))  # noqa: E731
    last = hist[-1]
    out = {"date": last["date"], "big_holder_ratio": last["big_holder_ratio"], "week_change_pct": None,
           "change_pp": None, "gap_days": None, "single_week": None, "streak_weeks": 0, "weeks_available": len(hist)}
    if len(hist) >= 2:
        prev = hist[-2]
        gap = (d(last["date"]) - d(prev["date"])).days
        chg = round(last["big_holder_ratio"] - prev["big_holder_ratio"], 4)
        out.update(change_pp=chg, gap_days=gap, single_week=gap <= 9)
        if gap <= 9:
            out["week_change_pct"] = chg
        else:
            out["reason"] = f"集保缺週：{prev['date']}→{last['date']} 相隔 {gap} 天，變化不是單週"
    # 連續增持週數：從最新往回數，遇到缺週（相隔 >9 天）就中斷
    for i in range(len(hist) - 1, 0, -1):
        gap = (d(hist[i]["date"]) - d(hist[i - 1]["date"])).days
        if gap > 9 or not hist[i]["big_holder_ratio"] > hist[i - 1]["big_holder_ratio"]:
            break
        out["streak_weeks"] += 1
    return out


def change_tags(rv, q, p, ins, hd, ev):
    t = []
    y, yp = rv.get("rev3_yoy"), rv.get("rev3_yoy_prev")
    if y is not None and yp is not None:
        if y >= 0.20 and y - yp >= 0.10: t.append("營收加速")
        if y > 0 >= yp: t.append("營收轉正")
        if y - yp <= -0.20 and y < 0.10: t.append("營收轉弱")
    if rv.get("rev_high_months"): t.append("營收創新高")
    if not q.get("q_stale") and q.get("gm_qoq_pp") is not None:
        if q["gm_qoq_pp"] >= 3: t.append("毛利率跳升")
        if q["gm_qoq_pp"] <= -3: t.append("毛利率轉差")
    if ev.get("next_call"): t.append("法說將至")
    if p.get("close") and p.get("hi60") and p["close"] >= p["hi60"] and p.get("vol5_20") is not None:
        if p["vol5_20"] >= 1.5: t.append("量增創 60 日新高")
        if p["vol5_20"] < 0.8: t.append("創高量縮")
    if any("帶量大跌" in f["tags"] for f in p.get("flags", [])[-3:]) and p.get("ma60") and p["close"] < p["ma60"]:
        t.append("量增跌破 60 日均線")
    if ins.get("trust_streak", 0) >= 5: t.append("投信連買")
    r20, f20 = p.get("ret20"), ins.get("foreign20")
    if r20 is not None and f20 is not None and not ins.get("foreign_missing_days") and ((r20 >= 0.10 and f20 < 0) or (r20 <= -0.10 and f20 > 0)):
        t.append("法人背離")
    if hd and hd.get("single_week") and (hd.get("week_change_pct") or 0) >= 0.5 and (hd.get("streak_weeks") or 0) >= 2:
        t.append("大戶增持")
    if ev.get("recent_major"): t.append("重大訊息")
    return t


def score(tags):
    return sum(2 if x in FUND_TAGS else 1 for x in tags)


# ---------------------------------------------------------------- L3 深度
def lab_deep(code, cfg, l1, fund_hist, asof_year):
    """research/lab/config/<代號>.json → 情境 EPS、論點追蹤、說法紀錄。"""
    out = {"name": cfg.get("name"), "headline": cfg.get("headline", ""), "doc_url": cfg.get("doc_url"),
           "next_checkpoints": cfg.get("next_checkpoints", []), "known_gaps": cfg.get("known_gaps", []),
           "thesis": {"statement": cfg["thesis"]["statement"], "confirmed_by_user": cfg["thesis"].get("confirmed_by_user", False)}}
    # 情境 EPS：EPS = 營收 ×（毛利率 − 費用率）×（1 − 稅率）／股數，業外 0
    sc = cfg["scenario"]
    h = [r for r in (fund_hist or []) if r["year"] == sc["base"]["year"]]
    ytd = sum(r["revenue"] for r in h)
    last_m = max((r["month"] for r in h), default=0)
    ytd_note = f"官方月營收 {len(h)} 個月"
    ov = sc["base"].get("ytd_override")  # 月營收不齊時（例：興櫃期間）由人工提供年初至今合計＋來源
    if len(h) < last_m:
        if ov and ov.get("through_month", 0) >= last_m:
            ytd, last_m, ytd_note = ov["value"], ov["through_month"], f"人工覆寫：{ov.get('source', '未註明')}"
        else:
            out["known_gaps"] = out["known_gaps"] + [f"{sc['base']['year']} 年月營收只有 {len(h)} 個月（到 {last_m} 月），情境起點偏低"]
    base = ytd + sc["base"]["assumed_monthly"] * (12 - last_m)
    shares = (l1["q"].get("shares_k") or 0) * 1000 or cfg.get("shares_fallback")
    price = l1["p"].get("close")
    rows = []
    for name, s in sc["scenarios"].items():
        rev = base * (1 + s["growth"])
        eps = rev * (s["gm"] - s["opex"]) * (1 - sc["tax"]) / shares if shares else None
        rows.append({"name": name, "growth": s["growth"], "gm": s["gm"], "opex": s["opex"], "revenue": round(rev),
                     "eps": None if eps is None else round(eps, 2), "pe_band": s["pe"],
                     "price_band": None if eps is None else [round(eps * s["pe"][0]), round(eps * s["pe"][1])],
                     "implied_pe": None if not (eps and price) else round(price / eps, 1), "basis": s.get("basis", "")})
    out["scenario"] = {"target_year": sc["target_year"], "base_revenue": round(base), "ytd": round(ytd), "ytd_month": last_m,
                       "assumed_monthly": sc["base"]["assumed_monthly"], "tax": sc["tax"], "shares": shares, "price": price,
                       "ytd_note": ytd_note, "rows": rows, "position": locate(price, rows), "must_deliver": sc.get("must_deliver", []),
                       "assumption_owner": sc.get("assumption_owner", "未確認")}
    # 論點追蹤：自動指標讀 L1，人工指標讀 config
    ind = []
    auto = {"rev3_yoy": l1["rv"].get("rev3_yoy"), "rev3_qoq": l1["rv"].get("rev3_qoq"),
            "gm": None if l1["q"].get("gm") is None or l1["q"].get("q_stale") else l1["q"]["gm"] / 100}
    for i in cfg.get("indicators", []):
        if i["kind"] == "manual":
            ind.append({k: i.get(k) for k in ("id", "group", "label", "status", "detail", "asof", "source", "support_text", "review_text")})
            continue
        v = auto.get(i["kind"])
        st = "no_data"
        if v is not None:
            st = "neutral"
            if i.get("review_if") and _cmp(v, i["review_if"]): st = "review"
            elif i.get("support_if") and _cmp(v, i["support_if"]): st = "support"
        ind.append({"id": i["id"], "group": i["group"], "label": i["label"], "value": r4(v), "status": st,
                    "reason": None if v is not None else (l1["q"].get("reason") if i["kind"] == "gm" else l1["rv"].get("reason") or "資料不足")})
    out["thesis"]["indicators"] = ind
    out["thesis"]["counts"] = {s: sum(1 for x in ind if x["status"] == s) for s in ("support", "neutral", "review", "no_data")}
    out["guidance"] = guidance(code)
    return out


def _cmp(v, rule):
    op, x = rule
    return {">=": v >= x, ">": v > x, "<=": v <= x, "<": v < x}[op]


def locate(price, rows):
    rs = [r for r in rows if r["price_band"]]
    if not price or not rs:
        return "無法定位"
    inside = [r["name"] for r in rs if r["price_band"][0] <= price <= r["price_band"][1]]
    if inside:
        return "、".join(inside) + "情境帶內"
    if price < rs[0]["price_band"][0]:
        return f"低於{rs[0]['name']}下緣"
    if price > rs[-1]["price_band"][1]:
        return f"高於{rs[-1]['name']}上緣"
    for a, b in zip(rs, rs[1:]):
        if a["price_band"][1] < price < b["price_band"][0]:
            return f"介於{a['name']}上緣與{b['name']}下緣之間"
    return "無法定位"


TOPICS = {"orders": "訂單與拉貨", "capacity": "產能與資本支出", "margin": "毛利率與產品組合", "new_product": "新產品量產與驗證",
          "bottleneck": "營運瓶頸", "guidance": "財測／營收目標", "other": "其他"}


def guidance(code):
    f = LAB / "guidance" / f"{code}.jsonl"
    recs, errs = [], []
    if f.exists():
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("topic") not in TOPICS or r.get("direction") not in (-1, 0, 1) or r.get("asof", "") > r.get("recorded_at", ""):
                errs.append(f"第 {i} 行格式錯誤（topic／direction／asof>recorded_at）")
                continue
            recs.append(r)
    by = {}
    for r in sorted(recs, key=lambda x: x["asof"]):
        by.setdefault(r["topic"], []).append(r)
    changes = []
    for t, rs in by.items():
        prev = rs[-2] if len(rs) > 1 else None
        d = None if prev is None else rs[-1]["direction"] - prev["direction"]
        changes.append({"topic": t, "topic_zh": TOPICS[t], "latest": rs[-1], "previous": prev,
                        "shift": None if d is None else ("轉強" if d > 0 else "轉弱" if d < 0 else "持平")})
    return {"records": recs, "changes": changes, "errors": errs, "status": "ok" if recs else "尚無說法紀錄"}


# ---------------------------------------------------------------- 主流程
def main():
    argv = sys.argv[1:]
    asof_arg = next((a.split("=", 1)[1] for a in argv if a.startswith("--asof=")), None)
    if asof_arg is None and "--asof" in argv and argv.index("--asof") + 1 < len(argv):  # 用法寫的是「--asof YYYY-MM-DD」，兩種都收
        asof_arg = argv[argv.index("--asof") + 1]
    now = dt.datetime.now(TZ)
    errors = []
    import price_history_store as PHS  # noqa: E402
    ph = PHS.load(DATA / "price_history.json").get("prices", {})
    fund = (load(DATA / "fundamentals.json", {}) or {}).get("fundamentals", {})
    sd = (load(DATA / "stock_detail.json", {}) or {}).get("stocks", {})
    ih = load(DATA / "institutional_history.json", {}) or {}
    ih_series, ih_dates = ih.get("series", {}), sorted(ih.get("dates", []))
    evs = (load(DATA / "events.json", {}) or {}).get("events", [])
    holders = (load(DATA / "holders.json", {}) or {}).get("stocks", {})
    # 研究室.二／三 回補檔（不存在就略過）：{"meta":…, "stocks": {代號: [列…]}}
    for name, target in (("revenue_backfill.json", REV_BACKFILL), ("financials_backfill.json", FIN_BACKFILL)):
        if (DATA / name).exists():
            target.update(((load(DATA / name, {}) or {}).get("stocks") or {}))
    comp = (load(DATA / "company_info.json", {}) or {}).get("companies", {})
    active = set((load(DATA / "listed_universe.json", {}) or {}).get("active", []))
    ev_by = {}
    for e in evs:
        ev_by.setdefault(e.get("code"), []).append(e)
    last_dates = sorted({rows[-1]["date"] for rows in ph.values() if rows})
    asof = dt.date.fromisoformat(asof_arg or (last_dates[-1] if last_dates else now.date().isoformat()))
    ih_dates = [x for x in ih_dates if x <= asof.strftime("%Y%m%d")]  # 先.一〇三-14：法人歷史截到 asof
    # 月營收／季報的「公告期限」截法只在指定 --asof 回放時用；每日正式產出（asof＝最新資料日）不截，
    # 否則每月 1～10 日會把已提早公告的上月營收、法定期限前已公告的季報丟掉。
    replay = asof_arg is not None
    cut_rv = (lambda h: cut_revenue(h, asof)) if replay else (lambda h: h)

    stocks = {}
    universe = sorted(c for c in active if not any(k in (comp.get(c, {}).get("industry") or "") for k in NON_STOCK_INDUSTRY)
                      and not c.startswith("0"))
    for code in universe:
        try:
            rv = revenue_metrics(cut_rv(merged_revenue(fund.get(code), code)))
            fin_c, bf_c = (cut_quarters((sd.get(code) or {}).get("financials"), FIN_BACKFILL.get(code), asof) if replay
                           else ((sd.get(code) or {}).get("financials"), FIN_BACKFILL.get(code)))
            q = quarter_metrics(fin_c, asof, bf_c)
            p = price_metrics(cut_prices(ph.get(code), asof))
            ins = inst_metrics(ih_series.get(code), ih_dates)
            hd = holder_metrics(holders.get(code), asof)
            ev = event_metrics(ev_by.get(code, []), asof)
            tags = change_tags(rv, q, p, ins, hd, ev)
            ratios = (fund.get(code) or {}).get("ratios") or {}
            if str(ratios.get("date") or "")[:10] > asof.isoformat():  # 只有最新快照、沒有歷史：晚於 asof 就不用
                ratios = {}
            gaps = [x for x in (rv.get("reason"), q.get("reason"), p.get("reason"), ins.get("reason")) if x]
            stocks[code] = {
                "name": comp.get(code, {}).get("name", ""), "industry": comp.get(code, {}).get("industry", ""),
                "rev": rv, "q": q, "val": {"per": ratios.get("per"), "pbr": ratios.get("pbr"), "date": ratios.get("date")},
                "px": p, "inst": ins,
                "holders": None if not hd else {k: hd.get(k) for k in ("date", "big_holder_ratio", "week_change_pct", "change_pp", "gap_days",
                                                                        "single_week", "streak_weeks", "reason") if k in hd},
                "events": ev, "change_tags": tags, "change_score": score(tags),
                "liquid": (p.get("turnover20") or 0) >= LIQ_MIN_TURNOVER, "gaps": gaps,
            }
        except Exception as e:  # noqa: BLE001
            errors.append(f"{code}: {type(e).__name__}: {e}")

    # L3 深度
    # 先.一一二-2a（2026-10-18）：研究室卡片要標「內容停在 MM/DD」（超過 14 天沒更新）。內容日＝設定檔 content_updated 欄位
    # （改設定時一併更新）；完整 git 歷史在時（本機），再跟該檔最後 commit 日取較新的。雲端是淺層 checkout，git 日期＝當班 HEAD，
    # 會讓所有檔看起來都是今天，所以淺層時不用 git 日期。
    def _content_updated(path: Path, cfg: dict) -> str | None:
        vals = [cfg.get("content_updated")] if cfg.get("content_updated") else []
        try:
            import subprocess
            shallow = subprocess.run(["git", "rev-parse", "--is-shallow-repository"], cwd=ROOT, capture_output=True, text=True, timeout=20).stdout.strip()
            if shallow == "false":
                g = subprocess.run(["git", "log", "-1", "--format=%cs", "--", str(path)], cwd=ROOT, capture_output=True, text=True, timeout=20).stdout.strip()
                if g:
                    vals.append(g)
        except Exception:  # noqa: BLE001 —— 查不到 git 就只用欄位
            pass
        return max(vals) if vals else None

    deep_list = []
    for f in sorted((LAB / "config").glob("*.json")) if (LAB / "config").exists() else []:
        code = f.stem
        try:
            cfg = json.loads(f.read_text(encoding="utf-8"))
            if code not in stocks:
                errors.append(f"{code}: 深度設定存在但不在全市場宇宙")
                continue
            l1 = {"rv": stocks[code]["rev"], "q": stocks[code]["q"], "p": stocks[code]["px"]}
            stocks[code]["deep"] = lab_deep(code, cfg, l1, cut_rv(merged_revenue(fund.get(code), code)), asof.year)
            d = stocks[code]["deep"]
            deep_list.append({"code": code, "name": stocks[code]["name"], "headline": d["headline"], "position": d["scenario"]["position"],
                              "counts": d["thesis"]["counts"], "next": (d["next_checkpoints"] or [None])[0], "doc_url": d.get("doc_url"),
                              "content_updated": _content_updated(f, cfg), "data_asof": asof.isoformat()})
        except Exception as e:  # noqa: BLE001
            errors.append(f"深度 {code}: {type(e).__name__}: {e}")
            traceback.print_exc()

    # L2 雷達
    liq = [c for c, s in stocks.items() if s["liquid"]]

    list_totals = {}  # 先.一一二-3：每張名單截斷前的總檔數（首頁「研究室：今天 N 檔有新變化」用；名單本身最多 30／50 檔）

    def top(pred, key, n=30, rev=True):
        xs = [c for c in liq if pred(stocks[c])]
        xs.sort(key=lambda c: (key(stocks[c]) is None, key(stocks[c]) if key(stocks[c]) is not None else 0), reverse=False)
        xs = sorted(xs, key=lambda c: key(stocks[c]) or 0, reverse=rev)[:n]
        return [{"code": c, "name": stocks[c]["name"], "industry": stocks[c]["industry"], "tags": stocks[c]["change_tags"],
                 "rev3_yoy": stocks[c]["rev"].get("rev3_yoy"), "gm_qoq_pp": stocks[c]["q"].get("gm_qoq_pp"),
                 "ret20": stocks[c]["px"].get("ret20"), "close": stocks[c]["px"].get("close")} for c in xs]

    specs = [  # (名單, 條件, 排序鍵[, 最多幾檔])
        ("綜合變化", lambda s: s["change_score"] >= 2, lambda s: s["change_score"] * 1e12 + (s["px"].get("turnover20") or 0), 50),
        ("營收加速", lambda s: "營收加速" in s["change_tags"], lambda s: (s["rev"]["rev3_yoy"] or 0) - (s["rev"]["rev3_yoy_prev"] or 0)),
        ("營收創新高", lambda s: "營收創新高" in s["change_tags"], lambda s: s["rev"].get("rev3_yoy")),
        ("毛利率跳升", lambda s: "毛利率跳升" in s["change_tags"], lambda s: s["q"].get("gm_qoq_pp")),
        ("營收轉弱", lambda s: "營收轉弱" in s["change_tags"], lambda s: -((s["rev"]["rev3_yoy"] or 0) - (s["rev"]["rev3_yoy_prev"] or 0))),
        ("法說將至", lambda s: "法說將至" in s["change_tags"], lambda s: s["px"].get("turnover20")),
        ("量增創 60 日新高", lambda s: "量增創 60 日新高" in s["change_tags"], lambda s: s["px"].get("vol5_20")),
        ("創高量縮", lambda s: "創高量縮" in s["change_tags"], lambda s: s["px"].get("ret20")),
        ("法人背離", lambda s: "法人背離" in s["change_tags"], lambda s: abs(s["px"].get("ret20") or 0)),
        ("重大訊息", lambda s: "重大訊息" in s["change_tags"], lambda s: s["px"].get("turnover20")),
    ]
    lists = {}
    for spec in specs:
        name, pred, key = spec[0], spec[1], spec[2]
        lists[name] = top(pred, key, *spec[3:])
        list_totals[name] = sum(1 for c in liq if pred(stocks[c]))
    # 產業營收熱度（全宇宙、不設流動性門檻）
    ind = {}
    for c, s in stocks.items():
        ind.setdefault(s["industry"] or "未分類", []).append(s)
    heat = []
    for name, ss in ind.items():
        ys = [s["rev"]["rev3_yoy"] for s in ss if s["rev"].get("rev3_yoy") is not None]
        if len(ys) < 5:
            continue
        rets = [s["px"]["ret20"] for s in ss if s["px"].get("ret20") is not None]
        heat.append({"industry": name, "n": len(ss), "n_rev": len(ys), "median_rev3_yoy": r4(statistics.median(ys)),
                     "share_rev_up": r4(sum(y > 0 for y in ys) / len(ys)),
                     "share_accel": r4(sum("營收加速" in s["change_tags"] for s in ss) / len(ss)),
                     "median_ret20": r4(statistics.median(rets)) if rets else None})
    heat.sort(key=lambda x: x["median_rev3_yoy"] or 0, reverse=True)
    # 涵蓋率（誠實揭露）
    cov = {"universe": len(universe), "built": len(stocks), "with_rev3_yoy": sum(s["rev"].get("rev3_yoy") is not None for s in stocks.values()),
           "with_rev3_qoq": sum(s["rev"].get("rev3_qoq") is not None for s in stocks.values()),
           "with_fresh_quarter": sum(not s["q"].get("q_stale") for s in stocks.values()),
           "with_foreign": sum(s["inst"].get("foreign_missing_days", 0) == 0 and (s["inst"].get("inst_days") or 0) > 0 for s in stocks.values()),
           "with_price60": sum(s["px"].get("ma60") is not None for s in stocks.values()),
           "with_inst10": sum((s["inst"].get("inst_days") or 0) >= 10 for s in stocks.values()), "liquid": len(liq),
           "with_holders": sum(bool(s.get("holders")) for s in stocks.values()),
           "with_holders_single_week": sum(bool(s.get("holders") and s["holders"].get("single_week")) for s in stocks.values()),
           "deep": len(deep_list)}
    meta = {"schema": SCHEMA, "generated_at": now.isoformat(timespec="seconds"), "asof": asof.isoformat(), "disclaimer": DISCLAIMER,
            "source": "repo 內既有檔（price_history/fundamentals/stock_detail/institutional_history/events/holders/company_info/listed_universe，若有 revenue_backfill／financials_backfill 一併合併）＋research/lab；零外部請求",
            "asof_cut": "價量／月營收（次月10日公告期限）／季報（法定期限）／法人／集保／本益比皆截到 asof，事件只用 asof 以前公告的" if asof_arg else "未指定 --asof：用最新資料",
            "rules": RULE_TEXT, "liquidity_min_turnover20": LIQ_MIN_TURNOVER, "coverage": cov, "list_totals": list_totals, "errors": errors[:200], "n_errors": len(errors),
            "not_a_factor": "凍結.二：本檔欄位不得進 scores*.json 或當選股權重"}
    (OUT / "research.json").write_text(json.dumps({"meta": meta, "stocks": stocks}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    # 研究室.五-4：自選股列研究狀態點（全宇宙、不設流動性門檻）。review＝有深度研究且論點指標有「需檢討」；
    # tags＝change_tags ≥2 個。只給 App 畫點用，不是分數。
    dots = {}
    for c, s in stocks.items():
        if s.get("deep") and (s["deep"]["thesis"]["counts"].get("review") or 0) > 0:
            dots[c] = "review"
        elif len(s["change_tags"]) >= 2:
            dots[c] = "tags"
    radar = {"meta": meta, "lists": lists, "industry_heat": heat, "deep": deep_list, "dots": dots}
    (OUT / "research_radar.json").write_text(json.dumps(radar, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"research.json {len(stocks)} 檔；雷達綜合 {len(lists['綜合變化'])}；深度 {len(deep_list)}；錯誤 {len(errors)}；涵蓋 {cov}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001  守門員自身失敗只警告（CLAUDE.md 十二）
        traceback.print_exc()
        print(f"::warning::build_research 失敗：{e}")
    sys.exit(0)
