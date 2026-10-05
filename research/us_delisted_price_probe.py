# -*- coding: utf-8 -*-
"""先.十九-一／二：下市股價格覆蓋實測＋下市原因分類（**不計任何報酬**）。

總司令 2026-10-05【先.十九】：
  一、從新名冊 2012～2020 年 delisted 的普通股隨機抽 60 檔（固定種子），逐檔測
      yfinance 能否取得下市前任何日價；報有價格檔數、平均可用年數、最後價格日
      距下市日天數。同 60 檔測 Stooq **免 key 公開 CSV 端點**是否有資料
      （只讀公開端點，不領 key、不繞 CAPTCHA——取得方式鐵律）。
  二、下市原因分類：Form 25 日期前後 90 天內有 8-K Item 2.01／DEFM14A／SC TO-T／
      15-12G／15-15D → merger_or_going_private；Chapter 11／7 的 8-K Item 1.03 →
      bankruptcy；其餘 unknown。逐年報三類檔數。

ticker 問題（誠實揭露）：新名冊以 CIK 為主鍵，**早已下市的公司通常沒有現用 ticker**。
本腳本的 ticker 來源依序為 (a) 舊名冊 us_universe_pit.v1.bak.json 的 ticker 欄
(b) SEC submissions 端點的 tickers 欄。兩者都查不到者記 no_ticker 並計入分母——
因為「查不到代號所以測不了價格」在實務上等同「拿不到價格」，不得從分母剔除。

SEC 禮儀：sleep 0.2 秒；Stooq 為公開靜態 CSV，同樣 sleep 0.2 秒。全部落地快取。

用法：python research/us_delisted_price_probe.py --sample --price --reason
"""
from __future__ import annotations

import csv
import io
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
RAW = HERE / "data" / "raw"
CACHE = RAW / "us_delist_probe"
CACHE.mkdir(parents=True, exist_ok=True)
UNI = HERE / "data" / "us_universe_pit.json"
UNI_V1 = HERE / "data" / "us_universe_pit.v1.bak.json"
STATE = RAW / "us_universe_rebuild_state.json"
OUT = HERE / "data" / "us_delisted_price_probe.json"
HEADERS = {"User-Agent": "AlphaResearch-USTrack contact@alpha-research-project.example",
           "Accept-Encoding": "gzip, deflate"}
SLEEP = 0.2
SEED = 20261005
N_SAMPLE = 60

MERGER_FORMS = ("DEFM14A", "SC TO-T", "15-12G", "15-15D", "15-12B")
_last = [0.0]


def _wait():
    d = SLEEP - (time.monotonic() - _last[0])
    if d > 0:
        time.sleep(d)
    _last[0] = time.monotonic()


def get_json(url: str, name: str):
    p = CACHE / name
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    _wait()
    try:
        r = requests.get(url, headers=HEADERS, timeout=60)
    except Exception as e:  # noqa: BLE001
        return {"_err": f"{type(e).__name__}: {e}"}
    if r.status_code != 200:
        d = {"_http": r.status_code}
        p.write_text(json.dumps(d), encoding="utf-8")
        return d
    try:
        d = r.json()
    except Exception:  # noqa: BLE001
        return {"_err": "non-json"}
    p.write_text(json.dumps(d), encoding="utf-8")
    return d


def pick_sample() -> list[dict]:
    uni = json.loads(UNI.read_text(encoding="utf-8"))["universe"]
    pool = [v for v in uni.values()
            if v.get("status") == "delisted" and "2012" <= (v.get("delisted_at") or "")[:4] <= "2020"]
    pool.sort(key=lambda v: int(v["cik"]))          # 先排序再抽，確保可重現
    rng = random.Random(SEED)
    sample = rng.sample(pool, min(N_SAMPLE, len(pool)))
    # 補 ticker
    old = {}
    if UNI_V1.exists():
        for t, v in (json.loads(UNI_V1.read_text(encoding="utf-8")).get("universe") or {}).items():
            if v.get("cik"):
                old.setdefault(int(v["cik"]), t)
    for s in sample:
        cik = int(s["cik"])
        tk = s.get("ticker") or old.get(cik)
        if not tk:
            d = get_json(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", f"SUB_{cik}.json")
            tks = (d.get("tickers") or []) if isinstance(d, dict) else []
            tk = tks[0] if tks else None
        s["probe_ticker"] = tk
    return sample


def probe_yfinance(sample: list[dict]) -> list[dict]:
    import yfinance as yf
    rows = []
    for i, s in enumerate(sample):
        tk, cik, dl = s.get("probe_ticker"), int(s["cik"]), s["delisted_at"]
        rec = {"cik": cik, "name": s.get("name"), "ticker": tk, "delisted_at": dl}
        if not tk:
            rec.update({"has_price": False, "reason": "no_ticker"})
            rows.append(rec)
            continue
        try:
            df = yf.Ticker(tk).history(start="2005-01-01", end=dl, auto_adjust=False)
        except Exception as e:  # noqa: BLE001
            rec.update({"has_price": False, "reason": f"error:{type(e).__name__}"})
            rows.append(rec)
            continue
        if df is None or df.empty:
            rec.update({"has_price": False, "reason": "empty"})
        else:
            d0 = df.index[0].date()
            d1 = df.index[-1].date()
            dld = datetime.strptime(dl, "%Y-%m-%d").date()
            rec.update({"has_price": True, "n_rows": int(len(df)),
                        "first": str(d0), "last": str(d1),
                        "years_available": round((d1 - d0).days / 365.25, 2),
                        "days_last_to_delist": (dld - d1).days})
        rows.append(rec)
        print(f"  [{i + 1}/{len(sample)}] {tk or '(無代號)'} {dl} → {rec.get('has_price')}", flush=True)
    return rows


def probe_stooq(sample: list[dict]) -> list[dict]:
    """Stooq 免 key 公開 CSV（https://stooq.com/q/d/l/?s=xxx.us&i=d）。
    只打公開端點，不領 key、不過 CAPTCHA、不改 UA 偽裝瀏覽器。"""
    rows = []
    for s in sample:
        tk = s.get("probe_ticker")
        rec = {"cik": int(s["cik"]), "ticker": tk, "delisted_at": s["delisted_at"]}
        if not tk:
            rec.update({"has_price": False, "reason": "no_ticker"})
            rows.append(rec)
            continue
        p = CACHE / f"STOOQ_{tk}.csv"
        if p.exists():
            txt = p.read_text(encoding="utf-8", errors="replace")
        else:
            _wait()
            try:
                r = requests.get(f"https://stooq.com/q/d/l/?s={tk.lower()}.us&i=d",
                                 headers=HEADERS, timeout=60)
                txt = r.text if r.status_code == 200 else f"_HTTP_{r.status_code}"
            except Exception as e:  # noqa: BLE001
                txt = f"_ERR_{type(e).__name__}"
            p.write_text(txt, encoding="utf-8")
        if txt.startswith("_") or "Date," not in txt:
            rec.update({"has_price": False, "reason": "no_data_or_blocked",
                        "snippet": txt[:60]})
        else:
            rd = list(csv.DictReader(io.StringIO(txt)))
            before = [x for x in rd if x.get("Date", "") < s["delisted_at"]]
            rec.update({"has_price": bool(before), "n_rows_before_delist": len(before),
                        "first": before[0]["Date"] if before else None,
                        "last": before[-1]["Date"] if before else None})
        rows.append(rec)
    return rows


def classify_reasons(sample: list[dict]) -> list[dict]:
    from datetime import date, timedelta
    rows = []
    for s in sample:
        cik, dl = int(s["cik"]), s["delisted_at"]
        d = get_json(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", f"SUB_{cik}.json")
        rec = {"cik": cik, "ticker": s.get("probe_ticker"), "delisted_at": dl}
        recent = (d.get("filings", {}) or {}).get("recent", {}) if isinstance(d, dict) else {}
        forms = recent.get("form") or []
        dates = recent.get("filingDate") or []
        items = recent.get("items") or [""] * len(forms)
        dld = date.fromisoformat(dl)
        lo, hi = dld - timedelta(days=90), dld + timedelta(days=90)
        hit_m, hit_b = [], []
        for f, fd, it in zip(forms, dates, items):
            try:
                fdd = date.fromisoformat(fd)
            except Exception:  # noqa: BLE001
                continue
            if not (lo <= fdd <= hi):
                continue
            fu = str(f).upper()
            if fu.startswith("8-K") and "1.03" in str(it):
                hit_b.append(f"{f}@{fd}(1.03)")
            elif fu.startswith("8-K") and "2.01" in str(it):
                hit_m.append(f"{f}@{fd}(2.01)")
            elif any(fu.startswith(x) for x in MERGER_FORMS):
                hit_m.append(f"{f}@{fd}")
        if hit_b:
            cat = "bankruptcy"
        elif hit_m:
            cat = "merger_or_going_private"
        else:
            cat = "unknown"
        rec.update({"category": cat, "evidence": (hit_b + hit_m)[:5],
                    "n_filings_in_window": sum(1 for fd in dates
                                               if fd and lo <= _safe_date(fd) <= hi)})
        rows.append(rec)
    return rows


def _safe_date(s: str):
    from datetime import date
    try:
        return date.fromisoformat(s)
    except Exception:  # noqa: BLE001
        return date(1900, 1, 1)


def main() -> int:
    args = sys.argv[1:] or ["--sample", "--price", "--reason"]
    res = {}
    if OUT.exists():
        try:
            res = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            res = {}
    res["generated_at"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    res["ruling"] = "先.十九-一／二"
    res["seed"] = SEED
    res["note"] = "只測資料可得性與下市原因，不計算任何報酬；holdout 未動"
    if "--sample" in args:
        s = pick_sample()
        res["sample"] = s
        print(f"抽樣 {len(s)} 檔（2012～2020 普通股下市，種子 {SEED}）；"
              f"其中有代號 {sum(1 for x in s if x.get('probe_ticker'))} 檔", flush=True)
    sample = res.get("sample", [])
    if "--price" in args and sample:
        print("=== yfinance ===", flush=True)
        res["yfinance"] = probe_yfinance(sample)
        print("=== Stooq（免 key 公開 CSV）===", flush=True)
        res["stooq"] = probe_stooq(sample)
    if "--reason" in args and sample:
        print("=== 下市原因分類 ===", flush=True)
        res["reasons"] = classify_reasons(sample)
    res["summary"] = summarize(res)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res["summary"], ensure_ascii=False, indent=1), flush=True)
    return 0


def summarize(res: dict) -> dict:
    out = {}
    yf_rows = res.get("yfinance") or []
    if yf_rows:
        ok = [r for r in yf_rows if r.get("has_price")]
        out["yfinance"] = {
            "n": len(yf_rows), "n_has_price": len(ok),
            "pct_has_price": round(100.0 * len(ok) / max(1, len(yf_rows)), 1),
            "n_no_ticker": sum(1 for r in yf_rows if r.get("reason") == "no_ticker"),
            "mean_years_available": round(sum(r["years_available"] for r in ok) / len(ok), 2) if ok else None,
            "mean_days_last_to_delist": round(sum(r["days_last_to_delist"] for r in ok) / len(ok), 1) if ok else None,
        }
    st = res.get("stooq") or []
    if st:
        ok = [r for r in st if r.get("has_price")]
        out["stooq"] = {"n": len(st), "n_has_price": len(ok),
                        "pct_has_price": round(100.0 * len(ok) / max(1, len(st)), 1)}
    rs = res.get("reasons") or []
    if rs:
        c = {}
        for r in rs:
            c[r["category"]] = c.get(r["category"], 0) + 1
        by_year = {}
        for r in rs:
            y = r["delisted_at"][:4]
            by_year.setdefault(y, {}).setdefault(r["category"], 0)
            by_year[y][r["category"]] += 1
        out["reasons"] = {"counts": c, "by_year": dict(sorted(by_year.items()))}
    if "yfinance" in out:
        p = out["yfinance"]["pct_has_price"]
        out["verdict_rule_4"] = ("美股線可進入先.十七（≥70%）" if p >= 70 else
                                 "資料不可及，美股線停、回報待裁示（<30%）" if p < 30 else
                                 "介於 30～70%：列兩種讀法交由總司令裁示")
    return out


if __name__ == "__main__":
    raise SystemExit(main())
