# -*- coding: utf-8 -*-
"""全市場資料一致性稽核（2026-09-06 總司令 P0「稽核.一」）。

**為什麼有這支腳本**
總司令實測看到「光聖 6442 現價 1755、建議進場價卻是 32」。根因查清楚了（見
PROGRESS.md 的證據鏈：報告頁 renderReport() 在 `peg=null` 上拋 TypeError 中途死掉，
上一檔昇貿 6808 的收盤 32 就留在畫面上），但總司令的裁示是「這是一類錯誤，不修單檔，
做結構性防線」——所以除了修那條崩潰，這支腳本負責**每天主動去找同一類問題**：
畫面上任何一個數字，只要跟官方資料對不起來，就要在使用者看到之前先被抓出來。

**設計原則**
- 只跟「官方交易所端點」比對，不拿我們自己的檔案互相背書（兩個檔案一起錯就驗不出來）。
- 查不到參考值時一律回報「無法查核」，**不算通過**。誠實比好看重要。
- 每一條違規都記下：哪一檔、哪一項檢查、哪個檔案、我們的值、官方的值、差多少。

**輸出**：`data/audit_report.json`（違規總數、違規率、分項統計、前 20 筆、完整清單）。
違規率 >1% 時冒煙測試會 FAIL（見 scripts/smoke_test.mjs 的資料稽核檢查）。

用法：`python scripts/data_audit.py`
"""
from __future__ import annotations

import json
import re
import ssl
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import certifi
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "audit_report.json"
TZ = timezone(timedelta(hours=8))

TWSE_STOCK_DAY_ALL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
TWSE_COMPANY = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
TPEX_QUOTES = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"
UA = {"User-Agent": "Mozilla/5.0 (compatible; AlphaDataAudit/1.0)"}

# 總司令定的容許值
TOL_PRICE_SOURCE = 0.05      # (a) 各檔案現價彼此/與官方差異
TOL_ENTRY_PLAN = 0.30        # (b) 建議進場價 vs 現價
TOL_RANGE_BREAK = 0.05       # (c) 允許當日突破 20 日高低點的幅度
TOL_MARKET_CAP = 0.05        # (d) 市值 ≈ 現價 × 股數
TOL_PE = 0.10                # (e) 本益比 = 現價 / EPS


class _StrictOffAdapter(HTTPAdapter):
    """TPEx 專用連線設定。

    Python 3.13 的 ssl.create_default_context() 預設開啟 VERIFY_X509_STRICT，會嚴格
    要求憑證鏈上的 CA 憑證都帶 Subject Key Identifier 擴充；TPEx 的中介 CA 沒有帶，
    於是這台機器上所有 tpex.org.tw 請求都掛在 `CERTIFICATE_VERIFY_FAILED: Missing
    Subject Key Identifier`（GitHub Actions 的 runner 用較舊的 OpenSSL，所以線上排程
    一直是好的，只有本機掛——查了很久才發現不是網路問題）。
    這裡**只**關掉那一項 RFC 5280 擴充檢查，憑證鏈驗證與主機名驗證都照常執行，
    不是 verify=False。
    """

    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.load_verify_locations(certifi.where())
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


def make_session() -> requests.Session:
    s = requests.Session()
    s.mount("https://", _StrictOffAdapter())
    s.headers.update(UA)
    return s


def num(v):
    """(g) 千分位逗號安全的數字解析。

    TWSE/TPEx 的 JSON 欄位是字串，且**價格超過一千就會帶千分位逗號**（'2,410.00'）。
    裸 float() 會拋 ValueError，被上游當成空值吞掉——這個 bug 讓千元以上股票的整條
    走勢線管線消失過兩次。任何解析交易所回傳字串的地方都必須走這支。
    """
    if v is None:
        return None
    s = str(v).strip().replace(",", "")
    if s in ("", "-", "--", "null", "None"):
        return None
    try:
        f = float(s)
    except (TypeError, ValueError):
        return None
    return f if f == f and abs(f) != float("inf") else None


def is_stock_code(code: str) -> bool:
    """普通股與 ETF；排除權證與帶字母的特別股（跟 fetch_quotes_tw.py 同一套規則）。"""
    if not code or not code.isdigit():
        return False
    return len(code) == 4 or (len(code) in (5, 6) and code.startswith("00"))


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # 檔案不存在/壞掉都要說出來，不能安靜跳過
        print(f"  ! 讀不到 {path.name}：{type(e).__name__} {e}")
        return None


# ──────────────────────────── 官方參考真值 ────────────────────────────
def fetch_reference(sess) -> tuple[dict, dict]:
    """回傳 (ref, meta)。ref: code -> {close, high, low, open, date, board}"""
    ref, meta = {}, {}
    try:
        rows = sess.get(TWSE_STOCK_DAY_ALL, timeout=90).json()
        n = 0
        for r in rows:
            code = str(r.get("Code", "")).strip()
            if not is_stock_code(code):
                continue
            close = num(r.get("ClosingPrice"))
            if close is None:
                continue
            ref[code] = {
                "close": close,
                "high": num(r.get("HighestPrice")),
                "low": num(r.get("LowestPrice")),
                "open": num(r.get("OpeningPrice")),
                "date": str(r.get("Date", "")),
                "board": "TWSE",
            }
            n += 1
        meta["twse"] = {"ok": True, "rows": len(rows), "usable": n}
    except Exception as e:
        meta["twse"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}

    try:
        rows = sess.get(TPEX_QUOTES, timeout=90).json()
        n = 0
        for r in rows:
            code = str(r.get("SecuritiesCompanyCode") or r.get("Code") or "").strip()
            if not is_stock_code(code):
                continue
            close = num(r.get("Close") or r.get("ClosingPrice"))
            if close is None:
                continue
            ref.setdefault(code, {
                "close": close,
                "high": num(r.get("High") or r.get("HighestPrice")),
                "low": num(r.get("Low") or r.get("LowestPrice")),
                "open": num(r.get("Open") or r.get("OpeningPrice")),
                "date": str(r.get("Date", "")),
                "board": "TPEx",
            })
            n += 1
        meta["tpex"] = {"ok": True, "rows": len(rows), "usable": n}
    except Exception as e:
        meta["tpex"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}

    return ref, meta


def fetch_shares(sess) -> tuple[dict, dict]:
    """上市公司流通股數 ≈ 實收資本額 / 每股面額（t187ap03_L）。上櫃無對應免費端點。"""
    shares, meta = {}, {}
    try:
        rows = sess.get(TWSE_COMPANY, timeout=90).json()
        for r in rows:
            code = str(r.get("公司代號", "")).strip()
            cap = num(r.get("實收資本額"))
            par = 10.0
            m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*元", str(r.get("普通股每股面額", "")))
            if m:
                p = num(m.group(1))
                if p:
                    par = p
            if is_stock_code(code) and cap and par:
                shares[code] = cap / par
        meta = {"ok": True, "rows": len(rows), "usable": len(shares),
                "note": "股數由「實收資本額 / 每股面額」推算，不扣庫藏股、不含特別股，本身是近似值"}
    except Exception as e:
        meta = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    return shares, meta


# ──────────────────────────── 七項恆等式檢查 ────────────────────────────
def rel_diff(a, b):
    if a is None or b is None or not b:
        return None
    return abs(a / b - 1)


class Audit:
    def __init__(self):
        self.violations: list[dict] = []
        self.stats: dict[str, dict] = {}

    def note(self, check, checked=0, unverifiable=0, note=""):
        s = self.stats.setdefault(check, {"checked": 0, "violations": 0, "unverifiable": 0, "note": ""})
        s["checked"] += checked
        s["unverifiable"] += unverifiable
        if note:
            s["note"] = note

    def hit(self, check, code, name, detail, ours, official, diff, source):
        self.stats.setdefault(check, {"checked": 0, "violations": 0, "unverifiable": 0, "note": ""})
        self.stats[check]["violations"] += 1
        self.violations.append({
            "check": check, "code": code, "name": name, "detail": detail,
            "ours": ours, "official": official,
            "diff_pct": round(diff * 100, 2) if diff is not None else None,
            "source": source,
        })


def check_a_price_sources(a, universe, ref, names, loc):
    """(a) 所有頁面的「現價」必須來自同一個真值。

    App 的規則是 live → quotes_tw → price_history 最後收盤。這裡把每一個會被讀到的
    檔案都跟官方收盤比一次，差超過 5% 就是違規——只要有一個檔案偏掉，某個頁面就會
    顯示跟其他頁面不一樣的價格。昇貿 6808 就是這樣被抓出來的（我們的檔案 66.8，
    官方 32.0，那份快照停在 2024-12-31 沒有更新）。
    """
    def from_hist(c):
        h = loc["price_hist"].get(c)
        return h[-1].get("close") if h else None

    files = {
        "quotes_all_tw.json": lambda c: (loc["quotes_all"].get(c) or {}).get("close"),
        "quotes_tw.json": lambda c: (loc["quotes_tw"].get(c) or {}).get("price"),
        "price_history.json": from_hist,
        "sparklines.json": lambda c: (loc["sparks"].get(c) or [None])[-1],
    }
    for code in universe:
        official = ref[code]["close"]
        for fname, getter in files.items():
            try:
                ours = num(getter(code))
            except Exception:
                ours = None
            if ours is None:
                a.note("a_price_source", unverifiable=1)
                continue
            a.note("a_price_source", checked=1)
            d = rel_diff(ours, official)
            if d is not None and d > TOL_PRICE_SOURCE:
                a.hit("a_price_source", code, names.get(code, ""),
                      fname + " 的現價與官方收盤不一致", ours, official, d, fname)


def _roc_to_iso(v):
    """TWSE 的日期是民國格式字串（'1150904'）。轉不出來就回 None，不猜。"""
    t = str(v or "").strip()
    if len(t) == 7 and t.isdigit():
        return "%04d-%s-%s" % (int(t[:3]) + 1911, t[3:5], t[5:7])
    if len(t) == 10 and t[4] == "-":
        return t
    return None


def check_a3_stale_price(a, ref, names, loc, boards, ref_date):
    """(a 延伸) 排行榜上的股票，本地價格日期不得落後官方最新交易日太多。

    a2 抓的是「這一檔根本不在名冊上」，這一條抓的是「還在名冊上、但我們手上的價格
    是好幾個月前的」——例如正峰 1538 仍在掛牌名冊裡，我們的價格卻停在 2024-12-31。
    使用者看到的是一個帶著日期標籤、看起來很正常的「現價」，實際上已經過期一年半。
    這就是總司令說的「一個不該出現的數字沒有關卡攔它」。
    """
    if not ref_date:
        a.note("a3_stale_price", note="官方參考日期解析不出來，本項無法查核")
        return
    limit_days = 10
    from datetime import date as _date
    try:
        y, m, d = (int(x) for x in ref_date.split("-"))
        ref_d = _date(y, m, d)
    except Exception:
        a.note("a3_stale_price", note="官方參考日期格式異常：" + str(ref_date))
        return

    for code in sorted(boards):
        if not is_stock_code(code):
            continue
        asof = None
        rec = loc["quotes_all"].get(code)
        if isinstance(rec, dict):
            asof = rec.get("date")
        if asof is None:
            h = loc["price_hist"].get(code)
            if h:
                asof = h[-1].get("date")
        if not asof:
            a.note("a3_stale_price", unverifiable=1)
            continue
        a.note("a3_stale_price", checked=1)
        try:
            y, m, d = (int(x) for x in str(asof).split("-"))
            lag = (ref_d - _date(y, m, d)).days
        except Exception:
            a.note("a3_stale_price", unverifiable=1)
            continue
        if lag > limit_days:
            a.hit("a3_stale_price", code, names.get(code, ""),
                  "這一檔在選股榜單上，但本地價格已落後官方最新交易日 " + str(lag) + " 天",
                  str(asof), ref_date, None, "quotes_all_tw.json / price_history.json")


def check_a2_not_in_official(a, ref, names, loc, official_only):
    """(a 延伸) 本地檔案裡有價格、但官方今日全市場快照查無此代號。

    這是稽核第一版漏掉、實測才發現的一類：昇貿 6808 在 quotes_all_tw / price_history /
    sparklines 裡都有資料，值是 66.8，日期停在 2024-12-31——但它今天不在 TWSE
    STOCK_DAY_ALL 也不在 TPEx 主板報價裡（FinMind 仍查得到 2026-09-04 收盤 32.0，
    所以它應該是轉到興櫃或改變掛牌狀態，不是完全停止交易）。
    結果就是 App 拿一個一年半前的價格當「現價」在顯示，而且因為官方快照沒有這一檔，
    上面每一條恆等式都「無法查核」而安靜跳過——**查不到就跳過等於白稽核**，所以
    這一類必須自己成為一條違規。
    """
    # 只看「App 真的會把它當成一檔現有股票顯示」的地方：三份選股榜單與自選股報價檔。
    # price_history / sparklines / quotes_all_tw 保留已下市股票的歷史是**正確**的
    # （歷史就是歷史，回測與因子計算都需要它），把那些也算成違規會製造 400 筆雜訊，
    # 把真正的問題淹掉——第一版就是這樣，修正後只留真的會被使用者看到的。
    surfaces = {
        "scores.json": set(),
        "scores_momentum.json": set(),
        "scores_future.json": set(),
        "quotes_tw.json": set(loc["quotes_tw"].keys()),
    }
    for sf in ("scores.json", "scores_momentum.json", "scores_future.json"):
        data = load_json(ROOT / sf) if (ROOT / sf).exists() else None
        if data:
            surfaces[sf] = {r.get("code") for r in data.get("stocks", []) if r.get("code")}

    seen = set()
    for fname, codes in surfaces.items():
        for code in sorted(codes):
            # 比對的是「官方在市名冊」而不是「今天有成交」——一檔股票今天沒有成交
            # 完全正常，不能因此判它下市（第一版就是拿當天快照比，把 34 檔只是當天
            # 沒成交的上櫃股誤標成下市）。名冊由 build_listed_universe.py 維護。
            if not is_stock_code(code) or code in official_only:
                continue
            a.note("a2_not_in_official", checked=1)
            key = (fname, code)
            if key in seen:
                continue
            seen.add(key)
            asof = None
            rec = loc["quotes_all"].get(code)
            if isinstance(rec, dict):
                asof = rec.get("date")
            if asof is None:
                h = loc["price_hist"].get(code)
                if h:
                    asof = h[-1].get("date")
            a.hit("a2_not_in_official", code, names.get(code, ""),
                  fname + " 會把這一檔當成現有股票顯示，但今日官方名冊查無此代號（已下市/停止交易）",
                  str(asof), "官方今日名冊無此代號", None, fname)
    # 歷史檔案裡的下市代號另外統計，屬於正常保留，不列為違規
    hist_only = {c for c in loc["price_hist"] if is_stock_code(c) and c not in ref}
    a.note("a2_not_in_official",
           note="歷史檔案（price_history）另有 " + str(len(hist_only)) +
                " 個已下市代號，屬正常歷史保留，不列違規")


def check_b_entry_plan(a, universe, ref, names, loc):
    """(b) 建議進場價/分批價必須在現價 ±30% 內。

    App 的分批價 = 該檔最後收盤 × {1.00, 0.96, 0.92}，價格來自 FinMind。這裡拿
    price_history 最後收盤（跟 FinMind 同樣是日線收盤，是同一個量）當代表算三檔
    進場價，任何一檔落在官方現價 ±30% 外就是違規——總司令看到的 32 vs 1755
    就會在這裡被攔下來。
    """
    for code in universe:
        official = ref[code]["close"]
        hist = loc["price_hist"].get(code)
        if not hist:
            a.note("b_entry_plan", unverifiable=1)
            continue
        base = num(hist[-1].get("close"))
        if base is None:
            a.note("b_entry_plan", unverifiable=1)
            continue
        a.note("b_entry_plan", checked=1)
        worst, worst_px = None, None
        for mult in (1.00, 0.96, 0.92):
            d = rel_diff(base * mult, official)
            if d is not None and (worst is None or d > worst):
                worst, worst_px = d, round(base * mult, 2)
        if worst is not None and worst > TOL_ENTRY_PLAN:
            a.hit("b_entry_plan", code, names.get(code, ""),
                  "依此價算出的分批進場價偏離現價超過 30%", worst_px, official, worst,
                  "price_history.json")


def check_c_range(a, universe, ref, names, loc):
    """(c) 20 日低點 ≤ 現價 ≤ 20 日高點（允許當日突破 5%）。"""
    for code in universe:
        official = ref[code]["close"]
        sp = loc["sparks"].get(code)
        vals = [num(x) for x in (sp or [])]
        vals = [v for v in vals if v is not None]
        if len(vals) < 5:
            a.note("c_range", unverifiable=1)
            continue
        a.note("c_range", checked=1)
        lo, hi = min(vals), max(vals)
        if official < lo * (1 - TOL_RANGE_BREAK):
            a.hit("c_range", code, names.get(code, ""), "現價低於 20 日低點超過 5%",
                  round(lo, 2), official, abs(official / lo - 1), "sparklines.json")
        elif official > hi * (1 + TOL_RANGE_BREAK):
            a.hit("c_range", code, names.get(code, ""), "現價高於 20 日高點超過 5%",
                  round(hi, 2), official, abs(official / hi - 1), "sparklines.json")


def check_d_market_cap(a, universe, ref, names, shares):
    """(d) 市值 ≈ 現價 × 流通股數（誤差 <5%）。

    誠實揭露：股數是用「實收資本額 / 每股面額」推算（TWSE t187ap03_L 的實收資本額、
    TPEx quotes 的 Capitals），沒有扣庫藏股、沒有處理特別股，本身就是近似值。所以
    這一項比對的是「股數資料是否跟官方資本額對得起來」，抓的是資料錯置與單位錯誤，
    不是精算市值——這一點在報告裡也會標明，不假裝它是精確查核。
    """
    for code in universe:
        official = ref[code]["close"]
        n = shares.get(code)
        if not n:
            a.note("d_market_cap", unverifiable=1)
            continue
        a.note("d_market_cap", checked=1)
        cap = official * n
        if cap <= 0:
            a.hit("d_market_cap", code, names.get(code, ""), "推算市值 ≤ 0（股數或價格資料有誤）",
                  cap, official, None, "t187ap03_L / TPEx Capitals")


def check_e_pe(a, universe, ref, names, loc):
    """(e) 本益比 = 現價 / 近四季 EPS，誤差 <10%。"""
    for code in universe:
        official = ref[code]["close"]
        fund = loc["fundamentals"].get(code) or {}
        per = num((fund.get("ratios") or {}).get("per"))
        detail = loc["stock_detail"].get(code) or {}
        qs = ((detail.get("financials") or {}).get("quarters") or [])
        last4 = qs[-4:]
        eps4 = [num(q.get("eps")) for q in last4]
        eps4 = [e for e in eps4 if e is not None]
        if per is None or len(eps4) < 4:
            a.note("e_pe", unverifiable=1)
            continue
        # 「近四季」必須真的是連續四季。實測發現 stock_detail.json 大量個股的季度序列
        # 中間缺一整年（例如台達電 2308 是 2024Q2→2024Q3→2024Q4→2026Q2，2025 全年不見），
        # 把這四筆加起來當 TTM EPS 是錯的。這種情況不是「本益比算錯」而是「季報資料
        # 有斷層」，要分開報，否則會把資料缺漏誤標成計算錯誤。
        seq = [(q.get("year"), q.get("quarter")) for q in last4]
        expected = []
        y, qq = seq[0]
        try:
            for _ in range(4):
                expected.append((y, qq))
                qq += 1
                if qq > 4:
                    qq, y = 1, y + 1
        except TypeError:
            expected = []
        # 除了連續，最新那一季還必須夠新。TWSE BWIBBU_ALL 的本益比一定是用最新四季算的，
        # 拿我們手上停在 2024 年的四季去比，差幾百 % 是必然結果，那是「資料過期」不是
        # 「本益比算錯」——第一版沒有分開，368 檔裡混了大量過期案例。
        now = datetime.now(TZ)
        cur_q = (now.year, (now.month - 1) // 3 + 1)
        last_q = seq[-1]
        try:
            stale = (cur_q[0] * 4 + cur_q[1]) - (last_q[0] * 4 + last_q[1]) > 3
        except TypeError:
            stale = True
        if stale:
            a.note("e_quarters_stale", checked=1)
            a.hit("e_quarters_stale", code, names.get(code, ""),
                  "stock_detail 的最新季報過舊（超過三季沒更新），算出來的近四季 EPS 不能代表現況",
                  str(last_q[0]) + "Q" + str(last_q[1]),
                  str(cur_q[0]) + "Q" + str(cur_q[1]) + " 當期", None, "stock_detail.json")
            continue
        if expected and seq != expected:
            a.note("e_quarters_gap", checked=1)
            a.hit("e_quarters_gap", code, names.get(code, ""),
                  "stock_detail 的季報序列不連續，算不出真正的近四季 EPS",
                  "-".join(str(x[0]) + "Q" + str(x[1]) for x in seq),
                  "連續四季", None, "stock_detail.json")
            continue
        ttm = sum(eps4)
        if ttm <= 0:
            a.note("e_pe", unverifiable=1)  # 虧損股沒有有意義的本益比
            continue
        a.note("e_pe", checked=1)
        implied = official / ttm
        d = rel_diff(per, implied)
        if d is not None and d > TOL_PE:
            a.hit("e_pe", code, names.get(code, ""),
                  "fundamentals 的本益比與「現價 / 近四季EPS」對不起來",
                  per, round(implied, 2), d, "fundamentals.json + stock_detail.json")


def check_f_null_as_number(a, loc):
    """(f) 任何數值欄位不得為 NaN/None 卻在 UI 顯示成數字。

    做兩件事：
    1. 掃輸出 JSON 有沒有 NaN/Infinity 字面（非法 JSON，瀏覽器 JSON.parse 會整包失敗）。
    2. 把 scores*.json 裡 factors[].raw 為 null 的欄位全部列出來，再回頭掃 index.html
       有沒有對這些欄位「無條件呼叫 .toFixed()」——光聖 6442 的 peg=null 就是這樣讓
       整個報告頁渲染中途拋錯、把上一檔的價格留在畫面上的。
    """
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    nan_pat = re.compile(r'(?<![A-Za-z_"])(NaN|Infinity|-Infinity)(?![A-Za-z_"])')
    for path in sorted(DATA.glob("*.json")) + [ROOT / "scores.json",
                                               ROOT / "scores_momentum.json",
                                               ROOT / "scores_future.json"]:
        if not path.exists():
            continue
        a.note("f_null_as_number", checked=1)
        if nan_pat.search(path.read_text(encoding="utf-8")):
            a.hit("f_null_as_number", "-", path.name,
                  "JSON 內含 NaN/Infinity 字面，瀏覽器 JSON.parse 會整包失敗",
                  "NaN/Infinity", "合法 JSON 數值或 null", None, path.name)

    null_fields = {}
    for sf in ("scores.json", "scores_momentum.json", "scores_future.json"):
        data = load_json(ROOT / sf) if (ROOT / sf).exists() else None
        if not data:
            continue
        for row in data.get("stocks", []):
            for fname, fval in (row.get("factors") or {}).items():
                for k, v in (fval.get("raw") or {}).items():
                    if v is None:
                        key = fname + "." + k
                        null_fields[key] = null_fields.get(key, 0) + 1

    for field, cnt in sorted(null_fields.items(), key=lambda kv: -kv[1]):
        leaf = field.split(".")[-1]
        a.note("f_null_as_number", checked=1)
        pat = re.compile(r"\." + re.escape(leaf) + r"\.toFixed\(")
        for m in pat.finditer(html):
            ls = html.rfind("\n", 0, m.start()) + 1
            le = html.find("\n", m.start())
            line = html[ls:le if le > 0 else len(html)]
            if (leaf + "!=null") in line.replace(" ", "") or "fact(" in line:
                continue
            a.hit("f_null_as_number", "-", field,
                  "index.html 對可能為 null 的 " + field +
                  " 無條件呼叫 .toFixed()，會讓整段渲染拋錯中止",
                  str(cnt) + " 檔此欄位為 null", "先判空再格式化", None, "index.html")
            break


def check_g_comma_parsing(a):
    """(g) 千分位逗號解析：掃所有抓取器，凡直接 float() 交易所回傳字串的一律列出。

    光聖那 32 最後查出是前端崩潰、不是逗號 bug，但總司令要求把這一項做成常態防線
    ——同一個 bug 在 fetch_quotes_tw.py 已經犯過兩次（第二次是修好之後在 rebase
    autostash 裡無聲消失的），靠人記得不可靠，要靠每晚掃描。
    """
    targets = sorted((ROOT / ".github" / "scripts").glob("*.py")) + \
        sorted((ROOT / "research").glob("*.py"))
    # 只掃「真的在解析交易所 JSON/CSV 回應」的檔案。第一版把整個 research/ 都掃了，
    # 結果 float(df["Close"].iloc[-1])、float(series.mean()) 這種 pandas/numpy 取值全被
    # 誤判（那些值本來就是數字，不是帶逗號的字串），94 筆裡絕大多數是誤報。
    exchange_src = re.compile(r"twse\.com\.tw|tpex\.org\.tw|taifex\.com\.tw", re.I)
    pandas_noise = re.compile(
        r"\.iloc|\.loc\[|\.mean\(|\.min\(|\.max\(|\.std\(|\.sum\(|\.median\(|"
        r"\.count\(|\.astype\(|\bnp\.|\bpd\.|_pct\b|iterrows")
    field_hint = re.compile(
        r"float\(\s*(?!str\()[^)\n]*?"
        r"(?:Price|Close|Open|High|Low|Volume|Value|Amount|Capitals|Shares|"
        r"\.get\(|row\[|r\[|rec\[|item\[|d\[)", re.I)
    for path in targets:
        try:
            src = path.read_text(encoding="utf-8")
        except Exception:
            continue
        if not exchange_src.search(src):
            continue
        a.note("g_comma_parsing", checked=1)
        for i, line in enumerate(src.splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if pandas_noise.search(line):
                continue
            if 'replace(",", "")' in line or "replace(',', '')" in line:
                continue
            if field_hint.search(line):
                a.hit("g_comma_parsing", "-",
                      str(path.relative_to(ROOT)) + ":" + str(i),
                      "直接 float() 交易所回傳字串，遇到千分位逗號會解析失敗變成空值",
                      line.strip()[:160], 'float(str(v).replace(",", ""))', None,
                      str(path.relative_to(ROOT)))


# ──────────────────────────── 主流程 ────────────────────────────
def main():
    started = datetime.now(TZ)
    print("Alpha 全市場資料一致性稽核")
    sess = make_session()

    print("抓官方參考真值…")
    ref, ref_meta = fetch_reference(sess)
    shares, shares_meta = fetch_shares(sess)
    for k, v in ref_meta.items():
        print("  " + k + ": " + json.dumps(v, ensure_ascii=False))
    print("  shares: " + json.dumps(shares_meta, ensure_ascii=False))

    if not ref:
        print("！完全拿不到官方參考值，稽核無法進行（不寫報告，避免留下一份看起來全過的假報告）")
        return 2

    ci = load_json(DATA / "company_info.json") or {}
    names = {c: (v or {}).get("name", "") for c, v in (ci.get("companies") or {}).items()}

    loc = {
        "quotes_all": (load_json(DATA / "quotes_all_tw.json") or {}).get("quotes", {}),
        "quotes_tw": (load_json(DATA / "quotes_tw.json") or {}).get("quotes", {}),
        "price_hist": (load_json(DATA / "price_history.json") or {}).get("prices", {}),
        "sparks": (load_json(DATA / "sparklines.json") or {}).get("sparklines", {}),
        "fundamentals": (load_json(DATA / "fundamentals.json") or {}).get("fundamentals", {}),
        "stock_detail": (load_json(DATA / "stock_detail.json") or {}).get("stocks", {}),
    }

    universe = sorted(ref.keys())
    print("稽核範圍：" + str(len(universe)) + " 檔（官方今日有收盤價的普通股/ETF）")

    listed = set()
    lu = load_json(DATA / "listed_universe.json")
    if lu:
        listed = set(lu.get("active") or [])
    if len(listed) < 1000:
        print("  ! listed_universe.json 不完整（" + str(len(listed)) +
              " 檔），改用今日官方快照當名冊，下市判定會偏嚴")
        listed = set(ref.keys())

    ref_date = None
    for v in ref.values():
        ref_date = _roc_to_iso(v.get("date"))
        if ref_date:
            break

    boards = set()
    for sf in ("scores.json", "scores_momentum.json", "scores_future.json"):
        data = load_json(ROOT / sf) if (ROOT / sf).exists() else None
        if data:
            boards |= {r.get("code") for r in data.get("stocks", []) if r.get("code")}

    a = Audit()
    check_a_price_sources(a, universe, ref, names, loc)
    check_a2_not_in_official(a, ref, names, loc, listed)
    check_a3_stale_price(a, ref, names, loc, boards, ref_date)
    check_b_entry_plan(a, universe, ref, names, loc)
    check_c_range(a, universe, ref, names, loc)
    check_d_market_cap(a, universe, ref, names, shares)
    check_e_pe(a, universe, ref, names, loc)
    check_f_null_as_number(a, loc)
    check_g_comma_parsing(a)

    # 違規率的分母是「有被檢查到的股票數」，不是檢查次數——總司令要看的是
    # 「多少檔股票身上有問題」，不是「跑了幾條斷言」。
    # 兩個指標分開算，因為它們是兩種不同的故障，混在一起會看不出重點：
    #   一致性違規 = 我們顯示的數字跟官方對不起來（總司令這次抓到的那一類，要擋 commit）
    #   完整度缺口 = 官方有、我們沒有或資料有斷層（屬於「稽核.二 覆蓋率補齊」的範圍）
    CONSISTENCY = {"a_price_source", "a2_not_in_official", "a3_stale_price",
                   "b_entry_plan", "c_range",
                   "d_market_cap", "e_pe", "f_null_as_number", "g_comma_parsing"}
    COMPLETENESS = {"e_quarters_gap", "e_quarters_stale"}
    bad_codes = {v["code"] for v in a.violations
                 if v["check"] in CONSISTENCY and v["code"] not in ("-", "")}
    code_free = [v for v in a.violations if v["check"] in CONSISTENCY and v["code"] in ("-", "")]
    gap_codes = {v["code"] for v in a.violations
                 if v["check"] in COMPLETENESS and v["code"] not in ("-", "")}
    rate = (len(bad_codes) / len(universe)) if universe else 0.0
    gap_rate = (len(gap_codes) / len(universe)) if universe else 0.0

    def sev(v):
        return -(v["diff_pct"] or 0)

    report = {
        "generated_at": started.isoformat(),
        "duration_sec": round((datetime.now(TZ) - started).total_seconds(), 1),
        "reference": {**ref_meta, "shares": shares_meta},
        "universe": len(universe),
        "reference_date": ref_date,
        "listed_universe_size": len(listed),
        "stocks_with_violation": len(bad_codes),
        "code_free_violations": len(code_free),
        "completeness_gap_stocks": len(gap_codes),
        "completeness_gap_rate": round(gap_rate, 5),
        "violation_rate": round(rate, 5),
        "violation_rate_gate": 0.01,
        "gate_pass": rate <= 0.01 and not code_free,
        "total_violations": len(a.violations),
        "by_check": a.stats,
        "top_20": sorted(a.violations, key=sev)[:20],
        "violations": a.violations,
        "notes": [
            "違規率分母＝官方今日有收盤價的普通股/ETF 檔數；分子＝身上至少一條違規的股票檔數。",
            "(d) 市值檢查的股數由實收資本額/面額推算，不扣庫藏股、不含特別股，屬近似查核。",
            "(f)(g) 是程式碼層級檢查，不綁定個股，計入 code_free_violations，"
            "有任何一筆就視同閘門不通過。",
            "violation_rate 只計「一致性」類（顯示的數字與官方對不起來）；季報斷層/過期屬於"
            "「完整度」類，另計 completeness_gap_rate，由稽核.二（覆蓋率補齊）負責收斂。",
        ],
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    print("")
    print("稽核完成：" + str(len(universe)) + " 檔")
    print("  一致性違規率 " + str(round(rate * 100, 2)) + "%（" + str(len(bad_codes)) +
          " 檔）＋ 程式碼層級 " + str(len(code_free)) + " 筆　門檻 1%　→ " +
          ("通過" if (rate <= 0.01 and not code_free) else "不通過"))
    print("  完整度缺口 " + str(round(gap_rate * 100, 2)) + "%（" + str(len(gap_codes)) +
          " 檔，季報斷層/過期，歸稽核.二處理）")
    for k, v in sorted(a.stats.items()):
        print("  " + k + ": 檢查 " + str(v["checked"]) + "、違規 " + str(v["violations"]) +
              "、無法查核 " + str(v["unverifiable"]))
    print("報告寫入 " + str(OUT.relative_to(ROOT)))
    return 0 if (rate <= 0.01 and not code_free) else 1


if __name__ == "__main__":
    sys.exit(main())
