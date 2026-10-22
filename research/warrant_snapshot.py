# -*- coding: utf-8 -*-
"""先.九十四-5a：權證每日基本資料＋收盤快照（供日後每檔每天反推隱含波動，見 research/WARRANT_DATA_SURVEY.md 第 5 節）。

為什麼要每天存：已到期權證的履約價／行使比例只在 mopsov（robots.txt 全站 Disallow，不抓），
官方開放資料只有「在市＋近 6 週到期」的，所以只能從今天起前向累積。

每天 7 次請求（官方都未公布上限，與 data/rate_limit_state.json 共用節流，同源間隔 ≥3 秒，
402/403/428/429 即封鎖該來源 2 小時、不重試、整輪停止）：
  1. TWSE openapi  t187ap37_L            上市權證基本資料彙總表（來源名 twse_openapi）
  2. TPEx openapi  mopsfin_t187ap37_O    上櫃權證基本資料彙總表（tpex_openapi）
  3. TPEx openapi  tpex_warrant_issue    上櫃發行基本資料（美式／歐式、重設、上市日、備註）（tpex_openapi）
  4-5. TWSE rwd MI_INDEX type=0999／0999P 上市認購／認售收盤（twse_mi_index）
  6-7. TPEx afterTrading/otc type=WW／EW  上櫃權證收盤／上櫃股票收盤（標的價）（tpex_www）

只留反推 IV 需要的欄位，gzip 存 research/data/warrant_snapshots/YYYY-MM-DD/。
research/data/ 在 .gitignore 裡，快照只存本機，不進 repo。
本程式不建排程（排程另案提案，見 docs/PROPOSAL_WARRANT_SNAPSHOT.md）。

用法：
  python research/warrant_snapshot.py                 # 抓今天（台北）
  python research/warrant_snapshot.py --date 2026-10-14
  python research/warrant_snapshot.py --from-raw DIR  # 不發請求，用既存原始回應重新解析

exit：0 完整、4 部分來源失敗（成功的照寫，meta.partial／failed_sources 記原因）、2 限流封鎖、3 驗證不過、1 全失敗。
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT_ROOT = HERE / "data" / "warrant_snapshots"
BLOCK = {402, 403, 428, 429}
TPE = timezone(timedelta(hours=8))

# (名稱, 節流來源名, URL, 參數產生函式)
REQUESTS = [
    ("twse_basic", "twse_openapi", "https://openapi.twse.com.tw/v1/opendata/t187ap37_L", lambda d: None),
    ("tpex_basic", "tpex_openapi", "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap37_O", lambda d: None),
    ("tpex_issue", "tpex_openapi", "https://www.tpex.org.tw/openapi/v1/tpex_warrant_issue", lambda d: None),
    ("twse_call", "twse_mi_index", "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX",
     lambda d: {"date": d.replace("-", ""), "type": "0999", "response": "json"}),
    ("twse_put", "twse_mi_index", "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX",
     lambda d: {"date": d.replace("-", ""), "type": "0999P", "response": "json"}),
    ("tpex_ww", "tpex_www", "https://www.tpex.org.tw/www/zh-tw/afterTrading/otc",
     lambda d: {"date": d.replace("-", "/"), "type": "WW", "response": "json"}),
    ("tpex_ew", "tpex_www", "https://www.tpex.org.tw/www/zh-tw/afterTrading/otc",
     lambda d: {"date": d.replace("-", "/"), "type": "EW", "response": "json"}),
]


def _num(v):
    if v is None:
        return None
    s = str(v).replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _roc_to_iso(v) -> str | None:
    """民國 1151013／115/10/13 或西元 2026/10/13、20261013 → 2026-10-13；認不得回 None。"""
    s = re.sub(r"[^0-9]", "", str(v or ""))
    if len(s) == 7:
        y, m, d = int(s[:3]) + 1911, int(s[3:5]), int(s[5:7])
    elif len(s) == 8:
        y, m, d = int(s[:4]), int(s[4:6]), int(s[6:8])
    else:
        return None
    return f"{y:04d}-{m:02d}-{d:02d}"


class Blocked(RuntimeError):
    pass


RETRY_WAIT_SEC = 60


def _conn_errors(requests) -> tuple:
    """連線中斷類例外；測試用的假 requests 沒有 exceptions 屬性時回空 tuple（不攔任何例外）。"""
    ex = getattr(requests, "exceptions", None)
    return tuple(c for c in (getattr(ex, "ConnectionError", None), getattr(ex, "ChunkedEncodingError", None)) if c)


def _get_once_retry(requests, wait_or_raise, src: str, name: str, url: str, params, sleep=None):
    """先.一〇九-8：10/16 tpex 檔下載到一半 ConnectionResetError 10054，整天快照沒存（權證快照只能當天抓）。
    只對「連線中斷類」（ConnectionError／ChunkedEncodingError，含連線逾時）等 60 秒重試一次；
    HTTP 狀態碼（含 402/403/428/429 限流）不在這裡重試——回應照常交回呼叫端判斷，不違反「額度用完不重試」。
    重試前照樣走節流（wait_or_raise），第二次再斷就把例外往外丟（main 照舊 exit 1）。"""
    import time
    exc = _conn_errors(requests)
    for attempt in (1, 2):
        wait_or_raise(src)
        try:
            return requests.get(url, params=params, timeout=120, headers={"User-Agent": "Mozilla/5.0"})
        except exc as e:
            if attempt == 2:
                raise
            print(f"  {name}: 連線中斷（{type(e).__name__}），{RETRY_WAIT_SEC} 秒後重試一次", flush=True)
            (sleep or time.sleep)(RETRY_WAIT_SEC)


def fetch_all(date: str, raw_dir: Path, failed: dict | None = None) -> dict:
    """發 7 次請求，原始回應 gzip 存 raw_dir（解析失敗時可重跑解析、不必重抓）。回傳 {名稱: 解出的 JSON}。

    先.一三二-3：10/16、10/21、10/22 tpex_basic（約 16MB）重試後仍 ChunkedEncodingError，舊版整輪拋錯，
    後面的上市收盤也沒抓、已抓的也沒寫。改為：單一來源連線中斷（重試一次後）／HTTP 錯誤／非 JSON
    只記進 failed {名稱: 原因}、跳過它、繼續下一個（請求次數不變：每個來源仍最多 1 次＋連線中斷重試 1 次）。
    402/403/428/429 照舊拋 Blocked、整輪停止（不改節流）。"""
    import requests
    from backfill_price_history_gaps import _rate_limit_record_block, _rate_limit_wait_or_raise

    failed = {} if failed is None else failed
    conn = _conn_errors(requests)
    raw_dir.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, src, url, pf in REQUESTS:
        f = raw_dir / f"{name}.json.gz"
        if f.exists():  # 同一天重跑不重抓
            out[name] = json.loads(gzip.decompress(f.read_bytes()).decode("utf-8"))
            continue
        try:
            r = _get_once_retry(requests, _rate_limit_wait_or_raise, src, name, url, pf(date))
        except conn as e:
            failed[name] = f"連線中斷，重試一次仍失敗（{type(e).__name__}: {str(e)[:160]}）"
            print(f"  {name}: {failed[name]}；略過此來源、繼續其他來源", flush=True)
            continue
        if r.status_code in BLOCK:
            _rate_limit_record_block(src, r.status_code, name)
            raise Blocked(f"{name} HTTP {r.status_code}，{src} 封鎖 2 小時，本輪停止")
        if r.status_code != 200:
            failed[name] = f"HTTP {r.status_code}"
            print(f"  {name}: {failed[name]}；略過此來源、繼續其他來源", flush=True)
            continue
        try:
            js = r.json()
        except ValueError:  # openapi 無效路徑會回 200＋HTML，不能只看狀態碼
            failed[name] = f"回傳不是 JSON（前 80 字：{r.text[:80]!r}）"
            print(f"  {name}: {failed[name]}；略過此來源、繼續其他來源", flush=True)
            continue
        f.write_bytes(gzip.compress(json.dumps(js, ensure_ascii=False).encode("utf-8")))
        out[name] = js
        print(f"  {name}: HTTP {r.status_code}，{len(r.content):,} bytes", flush=True)
    return out


def load_raw(raw_dir: Path) -> dict:
    # 只讀存在的原始回應（部分來源失敗那天缺檔；缺的不產出對應輸出檔）
    return {name: json.loads(gzip.decompress((raw_dir / f"{name}.json.gz").read_bytes()).decode("utf-8"))
            for name, *_ in REQUESTS if (raw_dir / f"{name}.json.gz").exists()}


def _key(row: dict, *prefixes) -> str:
    """openapi 欄位名有全形／半形括號差異，用正規化後的前綴比對找出實際鍵名。"""
    norm = {re.sub(r"[()（）\s]", "", k): k for k in row}
    for p in prefixes:
        p2 = re.sub(r"[()（）\s]", "", p)
        for nk, k in norm.items():
            if nk.startswith(p2):
                return k
    raise KeyError(f"欄位缺 {prefixes}；實際欄位：{list(row)}")


def parse_basic(rows: list) -> list:
    """t187ap37_L／mopsfin_t187ap37_O（欄位名相同）→ 只留 IV 反推需要的欄位。"""
    if not rows:
        return []
    r0 = rows[0]
    K = {
        "code": _key(r0, "權證代號"), "name": _key(r0, "權證簡稱"), "cp": _key(r0, "權證類型"),
        "kind": _key(r0, "類別"), "underlying": _key(r0, "標的證券/指數"),
        "strike": _key(r0, "最新履約價格"), "strike_orig": _key(r0, "原始履約價格"),
        "ratio_k": _key(r0, "最新標的履約配發數量"), "exercise_start": _key(r0, "履約開始日"),
        "last_trade": _key(r0, "最後交易日"), "expiry": _key(r0, "履約截止日"),
        "settle": _key(r0, "結算方式"), "units": _key(r0, "發行單位數量"), "report_date": _key(r0, "出表日期"),
        "remark": _key(r0, "備註"),
    }
    out = []
    for r in rows:
        ratio_k = _num(r.get(K["ratio_k"]))
        out.append({
            "code": str(r.get(K["code"], "")).strip(),
            "name": str(r.get(K["name"], "")).strip(),
            "cp": str(r.get(K["cp"], "")).strip(),
            "kind": str(r.get(K["kind"], "")).strip(),
            "underlying": str(r.get(K["underlying"], "")).strip(),
            "strike": _num(r.get(K["strike"])),
            "strike_orig": _num(r.get(K["strike_orig"])),
            "ratio": ratio_k / 1000 if ratio_k is not None else None,
            "exercise_start": _roc_to_iso(r.get(K["exercise_start"])),
            "last_trade": _roc_to_iso(r.get(K["last_trade"])),
            "expiry": _roc_to_iso(r.get(K["expiry"])),
            "settle": str(r.get(K["settle"], "")).strip(),
            "units": _num(r.get(K["units"])),
            "report_date": _roc_to_iso(r.get(K["report_date"])),
            # 備註含美式／歐式與除權息後履約價／行使比例調整紀錄，原文保留（空字串省略以省空間）
            "remark": str(r.get(K["remark"]) or "").strip() or None,
            "style": _style(r.get(K["remark"])),
        })
    return out


def _style(remark) -> str | None:
    """備註文字判斷美式／歐式；兩者都沒寫回 None（不猜）。"""
    t = str(remark or "")
    a, e = "美式" in t, "歐式" in t
    return "美式" if a and not e else "歐式" if e and not a else None


# tpex_warrant_issue 實測欄位（2026-10-14）：Date, Code, Name, ListedDate, ExpiryDate, UnderlyingStockCode,
# UnderlyingStock, Type, American/European, CapPrice/Index, FloorPrice/Index, Reset, LatestExercisePrice,
# "Latest ExerciseRatio", InitialIssuance, Accum.Accum.Issuance, Accum.CanceledWarrant（沒有備註欄）
KEEP_ISSUE = {"underlying_code": "UnderlyingStockCode", "style": "American/European", "reset": "Reset",
              "listed": "ListedDate", "expiry": "ExpiryDate", "strike": "LatestExercisePrice",
              "ratio": "Latest ExerciseRatio", "canceled_k": "Accum.CanceledWarrant", "type": "Type"}


def parse_tpex_issue(rows: list) -> dict:
    """tpex_warrant_issue → {代號: {標的代號、美式／歐式、重設、上市日…}}。"""
    out = {}
    for r in rows:
        code = str(r.get(_key(r, "Code"), "")).strip()
        rec = {}
        for k, src in KEEP_ISSUE.items():
            v = r.get(src)
            v = str(v).strip() if v is not None else None
            if k in ("strike", "ratio", "canceled_k"):
                v = _num(v)
            elif k in ("listed", "expiry"):
                v = _roc_to_iso(v)
            rec[k] = v
        out[code] = rec
    return out


def _table(js: dict, want: tuple[str, ...]):
    """TWSE rwd／TPEx www 回應 → (fields, data, title)；挑第一個含所有指定欄位的表。"""
    tables = js.get("tables") or []
    if not tables and js.get("fields"):
        tables = [js]
    for t in tables:
        fl = [str(x).strip() for x in t.get("fields") or []]
        if all(any(f.startswith(w) for f in fl) for w in want):
            return fl, t.get("data") or [], str(t.get("title") or js.get("title") or "")
    raise KeyError(f"找不到含 {want} 的表；表名：{[t.get('title') for t in tables]}")


def _ix(fields, name):
    for i, f in enumerate(fields):
        if f == name:
            return i
    for i, f in enumerate(fields):
        if f.startswith(name):
            return i
    raise KeyError(f"欄位缺「{name}」：{fields}")


def parse_quotes(js: dict, cols: dict, want: tuple[str, ...]) -> tuple[list, str]:
    fl, data, title = _table(js, want)
    idx = {k: _ix(fl, v) for k, v in cols.items()}
    out = []
    for row in data:
        rec = {}
        for k, i in idx.items():
            v = row[i] if i < len(row) else None
            v = re.sub(r"<[^>]+>", "", str(v)).strip() if v is not None else None
            rec[k] = v if k in ("code", "underlying") else _num(v)
        if rec.get("code"):
            out.append(rec)
    return out, title


TWSE_Q = {"code": "證券代號", "close": "收盤價", "volume": "成交股數", "bid": "最後揭示買價",
          "ask": "最後揭示賣價", "underlying": "標的代號", "und_close": "標的收盤價"}
TPEX_WW = {"code": "代號", "close": "收盤", "volume": "成交股數", "bid": "最後買價", "ask": "最後賣價"}
TPEX_EW = {"code": "代號", "close": "收盤"}


def build(raw: dict) -> dict:
    """raw 缺哪個來源（抓取失敗），就不產出依賴它的檔案（先.一三二-3）；不拿空值頂替。"""
    snap, titles = {}, {}
    if "twse_basic" in raw:
        snap["basic_twse"] = parse_basic(raw["twse_basic"])
    if "tpex_basic" in raw:
        snap["basic_tpex"] = parse_basic(raw["tpex_basic"])
    if "tpex_issue" in raw:
        snap["issue_tpex"] = parse_tpex_issue(raw["tpex_issue"])
    if "twse_call" in raw:
        snap["quotes_twse_call"], titles["twse_call"] = parse_quotes(raw["twse_call"], TWSE_Q, ("證券代號", "標的代號"))
    if "twse_put" in raw:
        snap["quotes_twse_put"], titles["twse_put"] = parse_quotes(raw["twse_put"], TWSE_Q, ("證券代號", "標的代號"))
    if "tpex_ww" in raw:
        snap["quotes_tpex"], titles["tpex_ww"] = parse_quotes(raw["tpex_ww"], TPEX_WW, ("代號", "最後買價"))
    if "tpex_ew" in raw and "issue_tpex" in snap:
        ew, titles["tpex_ew"] = parse_quotes(raw["tpex_ew"], TPEX_EW, ("代號", "收盤"))
        # 上櫃權證的標的價：WW 沒有，從 EW 取。基本資料表的「標的證券/指數」是名稱不是代號，
        # 標的代號要用 tpex_warrant_issue 的 UnderlyingStockCode；只留有上櫃權證掛在上面的標的。
        unders = {v["underlying_code"] for v in snap["issue_tpex"].values() if v.get("underlying_code")}
        snap["underlying_tpex"] = {r["code"]: r["close"] for r in ew if r["code"] in unders}
        titles["_underlying_tpex_missing"] = sorted(unders - set(snap["underlying_tpex"]))
    snap["_titles"] = titles
    return snap


def check(date: str, raw: dict, snap: dict) -> list:
    """寫檔前驗：日期核對（防『查不到就回別天』）＋各表不得為空。"""
    errs = []
    roc = f"{int(date[:4]) - 1911}年{date[5:7]}月{date[8:10]}日"
    for k in ("twse_call", "twse_put"):
        if k not in raw:  # 抓取失敗的來源記在 meta.failed_sources，不在這裡擋
            continue
        t = snap["_titles"].get(k, "")
        if roc not in t:
            errs.append(f"{k} title「{t}」不含 {roc}")
    for k in ("tpex_ww", "tpex_ew"):
        if k not in raw:
            continue
        rd = _roc_to_iso(raw[k].get("date"))
        if rd != date:
            errs.append(f"{k} 回應日期 {raw[k].get('date')} ≠ {date}")
    for k, v in snap.items():
        if not k.startswith("_") and not v:
            errs.append(f"{k} 為空")
    return errs


# 每個輸出檔依賴哪些原始來源（任一缺就不產出）
DEPENDS = {"basic_twse": ("twse_basic",), "basic_tpex": ("tpex_basic",), "issue_tpex": ("tpex_issue",),
           "quotes_twse_call": ("twse_call",), "quotes_twse_put": ("twse_put",), "quotes_tpex": ("tpex_ww",),
           "underlying_tpex": ("tpex_issue", "tpex_ew")}


def write(date: str, snap: dict, out_root: Path = OUT_ROOT, failed: dict | None = None) -> dict:
    d = out_root / date
    d.mkdir(parents=True, exist_ok=True)
    sizes = {}
    for k, v in snap.items():
        if k.startswith("_"):
            continue
        p = d / f"{k}.json.gz"
        p.write_bytes(gzip.compress(json.dumps(v, ensure_ascii=False, separators=(",", ":")).encode("utf-8")))
        sizes[k] = p.stat().st_size
    meta = {
        "date": date, "generated_at": datetime.now(TPE).isoformat(timespec="seconds"),
        "counts": {k: len(v) for k, v in snap.items() if not k.startswith("_")},
        "bytes_gz": sizes, "titles": {k: v for k, v in snap.get("_titles", {}).items() if not k.startswith("_")},
        # 上櫃權證的標的不在上櫃股票收盤（EW）裡的代號：通常是上市股票或指數，這天的標的價要另外拿
        "underlying_tpex_missing": snap.get("_titles", {}).get("_underlying_tpex_missing", []),
        "note": "先.九十四-5a 權證快照；欄位說明見 research/warrant_snapshot.py。非投資建議。",
    }
    if failed:
        # 先.一三二-3：部分來源抓取失敗時照寫成功的部分；缺的檔案與原因列在這裡，讀檔端要先看 partial
        meta["partial"] = True
        meta["failed_sources"] = dict(failed)
        meta["missing_files"] = sorted(k for k, deps in DEPENDS.items() if any(x in failed for x in deps))
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(TPE).strftime("%Y-%m-%d"))
    ap.add_argument("--from-raw", default=None, help="不發請求，從這個資料夾的原始回應解析")
    ap.add_argument("--keep-raw", action="store_true", help="保留原始回應（預設解析成功後刪除）")
    a = ap.parse_args()
    raw_dir = Path(a.from_raw) if a.from_raw else OUT_ROOT / "_raw" / a.date
    failed: dict = {}
    try:
        raw = load_raw(raw_dir) if a.from_raw else fetch_all(a.date, raw_dir, failed)
    except Blocked as e:
        print(f"[封鎖] {e}", flush=True)
        return 2
    if a.from_raw:
        failed.update({n: "原始回應檔不存在" for n, *_ in REQUESTS if n not in raw})
    if not raw:
        print("[全部來源都失敗，不寫檔] " + "；".join(f"{k}: {v}" for k, v in failed.items()), flush=True)
        return 1
    snap = build(raw)
    errs = check(a.date, raw, snap)
    if errs:
        print("[驗證不過，不寫檔；原始回應保留在 " + str(raw_dir) + "] " + "；".join(errs), flush=True)
        return 3
    meta = write(a.date, snap, failed=failed)
    if failed:
        # 部分成功：保留原始回應，同一天重跑只補抓失敗的來源；exit 4 讓排程記成失敗（不冒充完整快照）
        print(json.dumps({k: meta[k] for k in ("date", "counts", "failed_sources", "missing_files")},
                         ensure_ascii=False), flush=True)
        return 4
    print(json.dumps({k: meta[k] for k in ("date", "counts", "bytes_gz")}, ensure_ascii=False), flush=True)
    if not a.from_raw and not a.keep_raw:
        for f in raw_dir.glob("*.json.gz"):
            f.unlink()
        raw_dir.rmdir()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
