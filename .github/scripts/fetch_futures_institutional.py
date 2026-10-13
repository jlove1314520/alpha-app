# -*- coding: utf-8 -*-
"""先.八十一-10（2026-10-13）：期貨三大法人部位（台指期 TX 等）改由 repo 內檔案供應，FinMind 只當補充。

來源：TAIFEX 官方 openapi `v1/MarketDataOfMajorInstitutionalTradersDetailsOfFuturesContractsBytheDate`
（三大法人-區分各期貨契約-依日期；swagger 2026-10-13 查證）。回傳 CSV（開頭有 BOM），只給最新一個交易日，
本腳本每次把當日寫進 data/futures_institutional.json 的 history（依日期去重、保留最近 60 個交易日）。
欄位直接用官方中文欄名對應（不寫死欄位位置）。身份別：自營商／投信／外資及陸資。
頻率：官方未公布上限；market.yml 每日三班各 1 次請求，與 fetch_market_tw.py 共用 data/rate_limit_state.json
的節流／封鎖紀錄（來源名 taifex_openapi，同源最少間隔 3 秒，402/403/428/429 封鎖 2 小時不重試）。
失敗不覆蓋既有檔（App 會顯示資料日，落後時看得出來）。用法：python .github/scripts/fetch_futures_institutional.py
"""
import csv
import io
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT = REPO_ROOT / "data" / "futures_institutional.json"
STATE = REPO_ROOT / "data" / "rate_limit_state.json"
URL = "https://openapi.taifex.com.tw/v1/MarketDataOfMajorInstitutionalTradersDetailsOfFuturesContractsBytheDate"
SOURCE = "taifex_openapi"
KEEP_DAYS = 60
WHO = {"自營商": "dealer", "投信": "trust", "外資及陸資": "foreign"}
PRODUCTS = {"臺股期貨": "TX", "小型臺指期貨": "MTX", "微型臺指期貨": "TMF", "電子期貨": "TE", "金融期貨": "TF"}
FIELDS = {"long_oi": "多方未平倉口數", "short_oi": "空方未平倉口數", "net_oi": "多空未平倉口數淨額",
          "net_trade": "多空交易口數淨額", "net_oi_amount_k": "多空未平倉契約金額淨額(千元)"}
# 2026-10-13 實測：同一端點依內容協商有時回 CSV（中文欄名）、有時回 JSON（英文欄名）；GitHub Actions 上拿到的是 JSON，
# 第一版只認 CSV 而判定失敗。兩種都接受，欄位用名稱對應。
JSON_KEYS = {"date": "Date", "product": "ContractCode", "who": "Item",
             "long_oi": "OpenInterest(Long)", "short_oi": "OpenInterest(Short)", "net_oi": "OpenInterest(Net)",
             "net_trade": "TradingVolume(Net)", "net_oi_amount_k": "ContractValueofOpenInterest(Net)(Thousands)"}
TW = timezone(timedelta(hours=8))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"sources": {}}


def _gate():
    st = _state()
    src = st.setdefault("sources", {}).setdefault(SOURCE, {})
    now = time.time()
    if src.get("blocked_until") and now < src["blocked_until"]:
        raise RuntimeError(f"{SOURCE} 封鎖冷卻中（還剩約 {round((src['blocked_until'] - now) / 60, 1)} 分鐘），依資料源禮儀不送請求")
    if src.get("last_request_at") and now - src["last_request_at"] < 3.0:
        time.sleep(3.0 - (now - src["last_request_at"]))
    src["last_request_at"] = time.time()
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")


def _block(code: int):
    st = _state()
    src = st.setdefault("sources", {}).setdefault(SOURCE, {})
    src["blocked_until"] = time.time() + 2 * 3600
    src["block_reason"] = f"HTTP {code}（fetch_futures_institutional.py）"
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")


def _int(x):
    try:
        return int(str(x).replace(",", "").strip())
    except ValueError:
        return None


def parse(text: str) -> dict:
    """回傳 {日期ISO: {商品代碼: {foreign/trust/dealer: {欄位: 值}}}}。接受 JSON（英文欄名）或 CSV（中文欄名）。"""
    t = text.lstrip("﻿").lstrip()
    recs = []
    if t.startswith("["):
        for r in json.loads(t):
            recs.append((r.get(JSON_KEYS["product"]), r.get(JSON_KEYS["who"]), r.get(JSON_KEYS["date"]),
                         {k: _int(r.get(JSON_KEYS[k])) for k in FIELDS}))
    else:
        rows = list(csv.DictReader(io.StringIO(t)))
        if not rows or "商品名稱" not in rows[0] or "身份別" not in rows[0]:
            raise ValueError(f"回應既不是 JSON 陣列也不是預期的 CSV（開頭：{t[:60]!r}）")
        for r in rows:
            recs.append((r.get("商品名稱"), r.get("身份別"), r.get("日期"), {k: _int(r.get(v)) for k, v in FIELDS.items()}))
    out = {}
    for prod, who, d, vals in recs:
        p, w, d = PRODUCTS.get((prod or "").strip()), WHO.get((who or "").strip()), (d or "").strip()
        if not p or not w or len(d) != 8:
            continue
        iso = f"{d[:4]}-{d[4:6]}-{d[6:]}"
        out.setdefault(iso, {}).setdefault(p, {})[w] = vals
    if not out:
        raise ValueError("CSV 裡找不到任何目標商品（臺股期貨等）")
    return out


def main() -> int:
    try:
        _gate()
        r = requests.get(URL, headers={"User-Agent": "Mozilla/5.0 (compatible; AlphaAppMarketFetcher/1.0)",
                                       "Accept": "application/json"}, timeout=30)
        if r.status_code in (402, 403, 428, 429):
            _block(r.status_code)
            raise RuntimeError(f"HTTP {r.status_code}，已標記封鎖 2 小時")
        r.raise_for_status()
        r.encoding = "utf-8-sig"
        new = parse(r.text)
    except Exception as e:  # noqa: BLE001 — 任何失敗都不覆蓋既有檔
        print(f"[warn] 期貨三大法人抓取失敗，保留既有檔：{type(e).__name__}: {e}")
        return 0
    try:
        doc = json.loads(OUT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        doc = {}
    hist = {h["date"]: h for h in doc.get("history") or [] if isinstance(h, dict) and h.get("date")}
    for d, prods in new.items():
        hist[d] = {"date": d, "products": prods}
    rows = [hist[d] for d in sorted(hist)][-KEEP_DAYS:]
    doc = {"source": "TAIFEX openapi 三大法人-區分各期貨契約-依日期（MarketDataOfMajorInstitutionalTradersDetailsOfFuturesContractsBytheDate）",
           "fetched_at": datetime.now(TW).isoformat(timespec="seconds"),
           "data_date": rows[-1]["date"] if rows else None,
           "note": "口數；net_oi＝多空未平倉口數淨額（多方−空方）；每次排程累積當日，保留最近 60 個交易日",
           "history": rows}
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tx = (rows[-1]["products"].get("TX") or {}) if rows else {}
    print(f"futures_institutional：資料日 {doc['data_date']}，共 {len(rows)} 日；TX 外資未平倉淨額 {(tx.get('foreign') or {}).get('net_oi')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
