# -*- coding: utf-8 -*-
"""每日排程更新 data/customs_trade.json（財政部關務署海關進出口貿易統計）。

`PENDING_QUEUE.md`「源頭二.3」第9名：全國進出口貿易總額與出入超（貿易順逆差），
是總經面常態監控指標（`docs/FIRST_HAND_SOURCES.md` #19）。

資料源（財政部關務署官方開放資料，`https://data.gov.tw/dataset/6053`）：
`https://opendata.customs.gov.tw/data/6053/csv.csv`（免金鑰，CSV，官方每月更新，
2026-09-15實測回溯至民國103年1月即西元2014-01）。

**三來源查證（2026-09-15）**：①`data.gov.tw`資料集#6053頁面（WebSearch找到）
②WebFetch該頁面確認CSV下載網址、提供機關（財政部關務署）、更新頻率（每1月）
③實測`curl`與Python`requests`皆確認200、內容為合法CSV（`utf-8-sig`編碼、
含BOM），回溯150列（民國103年1月~115年6月）。

**已知SSL陷阱**（沿用`research/cbc_rf_rate_client.py`／`.github/scripts/
fetch_fx.py`記載的同一類修法）：`requests`預設驗證`opendata.customs.gov.tw`
會拋`CERTIFICATE_VERIFY_FAILED: Missing Subject Key Identifier`——這是台灣
政府機關憑證鏈裡中繼CA缺少該擴充欄位的共通問題（已在央行主機上遇過同一個
錯誤訊息），只關閉`ssl.VERIFY_X509_STRICT`這一個旗標，非`verify=False`。

**年度欄位是民國年**：CSV「年度」欄位為民國年（3位數字字串，例如`"115"`=
西元2026），本模組換算為西元年（民國年+1911）；資料為「反時間序」（最新月
在最前面），本模組讀入後不假設順序，改用`(year,month)`排序。

**單位**：CSV原始欄位單位為「新臺幣千元」，本模組原樣保留（不換算成億元，
避免精度/單位混淆），前端顯示時自行換算為較易讀的單位。
"""
from __future__ import annotations

import csv
import io
import json
import ssl
from datetime import datetime, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_PATH = REPO_ROOT / "data" / "customs_trade.json"

SOURCE_URL = "https://opendata.customs.gov.tw/data/6053/csv.csv"
SOURCE_LABEL = "財政部關務署官方開放資料（data.gov.tw #6053，海關進出口貿易統計），免金鑰"


class _StrictOffAdapter(requests.adapters.HTTPAdapter):
    """只關閉`ssl.VERIFY_X509_STRICT`這一個旗標，主機名稱驗證與CA信任鏈驗證
    維持開啟——見本檔docstring「已知SSL陷阱」段落，不是`verify=False`。"""

    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


def _fetch_rows() -> list[dict]:
    session = requests.Session()
    session.mount("https://", _StrictOffAdapter())
    resp = session.get(SOURCE_URL, timeout=20)
    resp.raise_for_status()
    text = resp.content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for raw in reader:
        try:
            roc_year = int(raw["年度"])
            month = int(raw["月份"])
        except (KeyError, ValueError, TypeError):
            continue
        try:
            rows.append({
                "year": roc_year + 1911,
                "month": month,
                "export_total": float(raw["出口總值(新臺幣千元)"]),
                "import_total": float(raw["進口總值(新臺幣千元)"]),
                "trade_balance": float(raw["出入超(新臺幣千元)"]),
            })
        except (KeyError, ValueError, TypeError):
            continue
    rows.sort(key=lambda r: (r["year"], r["month"]))
    return rows


def main() -> int:
    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": SOURCE_LABEL,
        "unit": "新臺幣千元",
        "note": "官方每月更新，資料通常落後1個月；出入超=出口總值-進口總值，正值為貿易順差、負值為逆差",
        "errors": [],
    }
    try:
        rows = _fetch_rows()
        if not rows:
            raise RuntimeError("解析後無有效資料列")
        latest = rows[-1]
        payload["latest"] = {
            "date": f"{latest['year']}-{latest['month']:02d}",
            "export_total": latest["export_total"],
            "import_total": latest["import_total"],
            "trade_balance": latest["trade_balance"],
        }
        target_year = latest["year"] - 1
        yoy_row = next((r for r in rows if r["year"] == target_year and r["month"] == latest["month"]), None)
        if yoy_row and yoy_row["export_total"] and yoy_row["import_total"]:
            payload["yoy"] = {
                "base_date": f"{yoy_row['year']}-{yoy_row['month']:02d}",
                "export_yoy_pct": round((latest["export_total"] / yoy_row["export_total"] - 1) * 100, 2),
                "import_yoy_pct": round((latest["import_total"] / yoy_row["import_total"] - 1) * 100, 2),
            }
        else:
            payload["yoy"] = None
            payload["errors"].append(f"回傳資料不含{target_year}-{latest['month']:02d}，無法計算YoY")
        payload["history_months"] = len(rows)
        print(f"最新 {payload['latest']['date']}：出口{latest['export_total']:.0f}千元 進口{latest['import_total']:.0f}千元 出入超{latest['trade_balance']:.0f}千元")
    except Exception as e:
        print(f"海關進出口統計抓取失敗：{e}")
        payload["errors"].append(f"customs_trade: {e}")
        payload["latest"] = None
        payload["yoy"] = None

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"寫入 {OUT_PATH}")
    return 0 if payload.get("latest") else 1


if __name__ == "__main__":
    raise SystemExit(main())
