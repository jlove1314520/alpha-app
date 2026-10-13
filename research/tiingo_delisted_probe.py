# -*- coding: utf-8 -*-
"""先.八十八-2～4：Tiingo 免費版已下市美股覆蓋率實測（**不計任何報酬、不登記試驗、不計 N**）。

總司令 2026-10-13【先.八十八】：用 先.八十七-1 固定的 60 檔已下市美股清單
（research/data/us_delisted_sample60.json），逐檔查 Tiingo metadata 與日線，另以 10 檔
在市大型股當對照組，確認不是 key 或程式本身的問題。

**額度（先.八十八-2，2026-10-14 查證）**
- 官方定價頁 <https://www.tiingo.com/about/pricing> 免費方案（Starter）原文：
  Max Requests Per Hour「50」、Max Requests Per Day「1000」、Unique Symbols per Month「500」、
  Max Bandwidth Per Month「1 GB」、Licensing「Internal Use Only」（只限自用、不得展示或分享給他人）。
- token 傳法：官方文件頁（/documentation/general/connecting）是 JS 渲染、純抓取拿不到原文；
  以社群客戶端 hydrosquall/tiingo-python `tiingo/api.py` 第 87 行
  `"Authorization": "Token {}".format(api_key)` 佐證（來源等級：社群，非官方白紙黑字）。
  本程式只用標頭傳 token，**不放在網址查詢字串**（避免留在任何存取紀錄）。
- 本程式硬限速（取官方 90%，[自行裁量]）：每小時 45、每天 900、每月 450 檔；
  狀態存在 data/raw/tiingo_quota_state.json（跨行程、跨輪次共用）。
  額度用完就停（exit 3），**不排隊、不重試、不換帳號、不換 IP**；下一個時窗再跑同一支，
  已拿到的結果有快取不會重抓。
- 授權「Internal Use Only」：結果只做研究用的覆蓋率統計；原始價格只存本機快取
  （data/raw/tiingo/，gitignore），**不進 repo、不上 App**。

**判定（照 CLAUDE.md「下市股：取得不等於正確」）**，每檔：
- `found`：metadata 回 200。
- `name_match`：Tiingo 名稱與 SEC 名稱的字詞重疊（排除 INC/CORP 等）；不符代表代號被沿用。
  SEC 端名稱＝清單名稱（form.idx 首見名，常是舊名）∪ submissions 現名 ∪ formerNames
  （讀 先.八十七-1 已快取的 data/raw/us_sample60/SUB_*.json.gz，不另打 SEC）。
  第一版只比清單名稱，BTFG（SEC 首見名 SOUTH ALABAMA BANCORPORATION、後改名 BancTrust）被誤判不符。
- `end_ok`：Tiingo 最後一筆日期落在 SEC 下市申報日 −20 天～＋45 天
  （Form 25 申報後約 10 天生效，[自行裁量] 給寬一點的窗）。
- `contaminated`：下市申報日＋45 天之後還有 >20 筆日線（代號沿用或 OTC 空殼續掛）。
- `start_ok`：Tiingo 第一筆 ≤ SEC 第一份定期報告日＋365 天（只是粗略的起點核對，
  1993 年以前上市者 SEC 端本來就沒有更早的申報可比）。
- `correct`＝found 且 name_match 且 end_ok 且 start_ok 且非 contaminated。
- `category`（另外分類，方便讀）：
  A 正確收尾／B 同公司下市後續掛（下市日前後 30 天內有 ≥10 筆、但之後還有大量資料，
  截斷在下市日才可用）／C 代號被別家沿用／D 有 metadata 沒價格／E 查不到／F 其他（片段或提早斷）。

用法：python research/tiingo_delisted_probe.py        # 跑到額度用完或全部做完
輸出：research/data/tiingo_delisted_probe.json（只含日期與筆數等統計，不含價格）
"""
from __future__ import annotations

import gzip
import json
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from collections import Counter
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SAMPLE = HERE / "data" / "us_delisted_sample60.json"
OUT = HERE / "data" / "tiingo_delisted_probe.json"
RAW = HERE / "data" / "raw" / "tiingo"
RAW.mkdir(parents=True, exist_ok=True)
QUOTA = HERE / "data" / "raw" / "tiingo_quota_state.json"
ENV = ROOT / ".env"
BASE = "https://api.tiingo.com/tiingo/daily"
LIM_HOUR, LIM_DAY, LIM_MONTH_SYMBOLS = 45, 900, 450
MIN_INTERVAL_SEC = 1.5
# 對照組：10 檔在市大型股（先.八十八-4 裁示原文舉 AAPL、MSFT）
CONTROLS = ["AAPL", "MSFT", "AMZN", "GOOGL", "JPM", "JNJ", "XOM", "PG", "KO", "WMT"]
STOP = {"INC", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LIMITED", "PLC", "HOLDINGS", "HOLDING",
        "GROUP", "THE", "OF", "AND", "LLC", "LP", "NV", "SA", "AG", "DE", "TRUST", "INTERNATIONAL", "INTL"}


class QuotaExhausted(Exception):
    pass


def _token() -> str:
    """只回傳值給 requests 用；任何地方都不印、不記錄。"""
    try:
        for line in ENV.read_text(encoding="utf-8").splitlines():
            if line.startswith("TIINGO_API_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception as e:  # noqa: BLE001
        print(f"  [.env 讀取失敗] {type(e).__name__}", flush=True)
    return ""


def _load_q() -> dict:
    try:
        return json.loads(QUOTA.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — 第一次跑沒有狀態檔是正常的
        return {"requests": [], "symbols": {}}


def _take(q: dict, symbol: str) -> None:
    """發送前檢查並登記額度；超過就丟 QuotaExhausted（硬拒絕，不等待）。"""
    now = time.time()
    q["requests"] = [t for t in q["requests"] if now - t < 86400]
    if sum(1 for t in q["requests"] if now - t < 3600) >= LIM_HOUR:
        raise QuotaExhausted(f"每小時上限 {LIM_HOUR}（官方 50）已用完")
    if len(q["requests"]) >= LIM_DAY:
        raise QuotaExhausted(f"每日上限 {LIM_DAY}（官方 1000）已用完")
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    syms = set(q["symbols"].get(month, []))
    if symbol not in syms and len(syms) >= LIM_MONTH_SYMBOLS:
        raise QuotaExhausted(f"每月 {LIM_MONTH_SYMBOLS} 檔（官方 500）已用完")
    syms.add(symbol)
    q["symbols"] = {month: sorted(syms)}
    if q["requests"]:
        wait = MIN_INTERVAL_SEC - (now - max(q["requests"]))
        if wait > 0:
            time.sleep(wait)
    q["requests"].append(time.time())
    QUOTA.write_text(json.dumps(q), encoding="utf-8")


def _get(q: dict, tok: str, symbol: str, path: str, cache: Path):
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    _take(q, symbol)
    try:
        r = requests.get(f"{BASE}/{path}", headers={"Authorization": f"Token {tok}",
                                                    "Content-Type": "application/json"}, timeout=60)
    except Exception as e:  # noqa: BLE001
        return {"_error": f"network:{type(e).__name__}"}
    if r.status_code == 429:
        raise QuotaExhausted("Tiingo 回 429")
    if r.status_code != 200:
        res = {"_error": f"HTTP {r.status_code}", "_body": r.text[:200]}
    else:
        try:
            res = r.json()
        except Exception:  # noqa: BLE001
            res = {"_error": "非 JSON", "_body": r.text[:200]}
    if "_error" not in res or res["_error"].startswith("HTTP 404"):
        cache.write_text(json.dumps(res), encoding="utf-8")
    return res


def _words(s: str) -> set[str]:
    return {w for w in re.findall(r"[A-Z0-9]+", (s or "").upper()) if w not in STOP and len(w) > 1}


SUB_CACHE = HERE / "data" / "raw" / "us_sample60"


def sec_names(rec: dict) -> list[str]:
    names = [rec["name"]]
    p = SUB_CACHE / f"SUB_{rec['cik']}.json.gz"
    try:
        sub = json.loads(gzip.decompress(p.read_bytes()).decode("utf-8", "replace"))
        names.append(sub.get("name") or "")
        names += [f.get("name") or "" for f in (sub.get("formerNames") or [])]
    except Exception as e:  # noqa: BLE001 — 讀不到就只用清單名稱，照實少比一點
        print(f"  [SEC 名稱快取讀不到，只比清單名稱] {rec['cik']}: {type(e).__name__}", flush=True)
    return [n for n in names if n]


def probe_one(q, tok, sym: str, rec: dict | None) -> dict:
    tk = sym.lower().replace(".", "-")
    meta = _get(q, tok, tk, tk, RAW / f"META_{tk}.json")
    row = {"ticker": sym, "found": "_error" not in meta and bool(meta.get("ticker"))}
    if not row["found"]:
        row["error"] = meta.get("_error")
        return row
    row.update(tiingo_name=meta.get("name"), tiingo_start=meta.get("startDate"),
               tiingo_end=meta.get("endDate"), tiingo_exchange=meta.get("exchangeCode"))
    px = _get(q, tok, tk, f"{tk}/prices?startDate=1990-01-01&resampleFreq=daily",
              RAW / f"PX_{tk}.json")
    dates = sorted(p["date"][:10] for p in px) if isinstance(px, list) else []
    row["n_rows"] = len(dates)
    row["first_row"], row["last_row"] = (dates[0], dates[-1]) if dates else (None, None)
    if isinstance(px, dict):
        row["prices_error"] = px.get("_error")
    if rec is None:
        return row
    dl = date.fromisoformat(rec["delisted_at"])
    sec_words = set().union(*[_words(n) for n in sec_names(rec)])
    ti_words = _words(meta.get("name"))
    row["name_overlap"] = sorted(sec_words & ti_words)
    row["name_match"] = bool(sec_words & ti_words)
    last = date.fromisoformat(row["last_row"]) if row["last_row"] else None
    first = date.fromisoformat(row["first_row"]) if row["first_row"] else None
    row["end_ok"] = bool(last and dl - timedelta(days=20) <= last <= dl + timedelta(days=45))
    row["rows_after_delist_45d"] = sum(1 for d in dates if date.fromisoformat(d) > dl + timedelta(days=45))
    row["contaminated"] = row["rows_after_delist_45d"] > 20
    fp = date.fromisoformat(rec["first_periodic_report"])
    row["start_ok"] = bool(first and first <= fp + timedelta(days=365))
    # 裁示要的是「起訖日涵蓋真正交易期間」，所以起點也要核對（ADPI 只有下市前 13 天，第一版誤算正確）
    row["correct"] = (row["found"] and row["name_match"] and row["end_ok"] and row["start_ok"]
                      and not row["contaminated"])
    row["rows_near_delist_30d"] = sum(1 for d in dates
                                      if dl - timedelta(days=30) <= date.fromisoformat(d) <= dl + timedelta(days=5))
    if row["correct"]:
        row["category"] = "A 正確收尾"
    elif not dates:
        row["category"] = "D 有 metadata 沒價格"
    elif not row["name_match"]:
        row["category"] = "C 代號被別家沿用"
    elif row["contaminated"] and row["rows_near_delist_30d"] >= 10:
        row["category"] = "B 同公司下市後續掛（需截斷）"
    else:
        row["category"] = "F 其他（片段或提早斷）"
    return row


def main() -> int:
    tok = _token()
    if not tok:
        print("本機 .env 沒有 TIINGO_API_TOKEN 或是空值，停止（先.八十八-1）", flush=True)
        return 4
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))["sample"]
    prev = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    done_d = {r["ticker"]: r for r in prev.get("delisted", [])}
    done_c = {r["ticker"]: r for r in prev.get("controls", [])}
    q = _load_q()
    stopped = None
    try:
        # 對照組先跑：key 或程式有問題時，對照組就會先失敗，不浪費下市股的額度
        for s in CONTROLS:
            if s not in done_c:
                done_c[s] = probe_one(q, tok, s, None)
                print(f"  對照 {s:6s} found={done_c[s]['found']} rows={done_c[s].get('n_rows')}", flush=True)
        if not all(r["found"] for r in done_c.values()):
            stopped = "對照組有查不到的，先停下檢查 key／程式，不繼續耗下市股額度"
        else:
            for rec in sample:
                s = rec["ticker"]
                if s in done_d and (RAW / f"META_{s.lower().replace('.', '-')}.json").exists()                         and (not done_d[s].get("found")
                             or (RAW / f"PX_{s.lower().replace('.', '-')}.json").exists()):
                    # 已完成者用快取重算判定（判定規則改了也會套用到舊結果，0 次請求）
                    r = probe_one(q, tok, s, rec)
                    if not r["found"]:
                        r["category"] = "E 查不到"
                    r.update(cik=rec["cik"], sec_name=rec["name"], delisted_at=rec["delisted_at"],
                             stratum=rec["stratum"], exchange=rec["exchange"])
                    done_d[s] = r
                    continue
                r = probe_one(q, tok, s, rec)
                if not r["found"]:
                    r["category"] = "E 查不到"
                r.update(cik=rec["cik"], sec_name=rec["name"], delisted_at=rec["delisted_at"],
                         stratum=rec["stratum"], exchange=rec["exchange"])
                done_d[s] = r
                print(f"  {s:7s} found={r['found']} end={r.get('tiingo_end')} vs 下市 {rec['delisted_at']} "
                      f"correct={r.get('correct')}", flush=True)
    except QuotaExhausted as e:
        stopped = f"額度：{e}（下一個時窗再跑同一支，已完成的有快取）"
    d = list(done_d.values())
    n = len(sample)

    def pct(k):
        return round(100.0 * sum(1 for r in d if r.get(k)) / max(1, n), 1)

    doc = {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "ruling": "先.八十八-2～4",
        "note": "只有日期與筆數統計，不含價格（Tiingo 免費版授權 Internal Use Only）；不計報酬、不登記試驗、不計 N",
        "limits": {"official": {"per_hour": 50, "per_day": 1000, "symbols_per_month": 500},
                   "ours": {"per_hour": LIM_HOUR, "per_day": LIM_DAY, "symbols_per_month": LIM_MONTH_SYMBOLS}},
        "progress": {"delisted_done": len(d), "delisted_total": n,
                     "controls_done": len(done_c), "stopped": stopped},
        "summary": {"n_sample": n, "found_pct": pct("found"), "name_match_pct": pct("name_match"),
                    "end_ok_pct": pct("end_ok"), "contaminated_pct": pct("contaminated"),
                    "start_ok_pct": pct("start_ok"), "correct_pct": pct("correct"),
                    "controls_found": f"{sum(1 for r in done_c.values() if r['found'])}/{len(done_c)}",
                    "by_category": dict(sorted(Counter(r.get("category", "?") for r in d).items()))},
        "controls": list(done_c.values()),
        "delisted": d,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n進度 下市 {len(d)}/{n}、對照 {len(done_c)}/{len(CONTROLS)}；停止原因：{stopped}", flush=True)
    print(f"摘要 {doc['summary']}", flush=True)
    return 3 if stopped and stopped.startswith("額度") else (0 if not stopped else 5)


if __name__ == "__main__":
    raise SystemExit(main())
