# -*- coding: utf-8 -*-
"""抓 USD/TWD 匯率，寫成 data/fx.json。

2026-09-15 更新（源頭二.3 第7名，`docs/FIRST_HAND_SOURCES.md` #21）：主來源改為
中央銀行外匯局官方牌告匯率 CSV（`FTDOpenData015.csv`，銀行間每日收盤即期匯率，
`data.gov.tw` 資料集 #7232，2016-01-01 起每日更新，回溯至 2008-01-02），
取代原本的 yfinance `TWD=X`；yfinance 降級為備援，央行端點失敗時才用，
維持「每個關鍵欄位要有回退鏈」的資料原則，不做單點依賴。

**SSL 已知問題**（沿用 `research/cbc_rf_rate_client.py` 記載的同一個修法）：
`requests` 預設驗證 `www.cbc.gov.tw` 會拋 `CERTIFICATE_VERIFY_FAILED: Missing
Subject Key Identifier`——這是央行憑證鏈裡某張中繼 CA 缺少 `Subject Key
Identifier` 擴充欄位，不是憑證過期或偽造。只關閉 `ssl.VERIFY_X509_STRICT`
這一個較新且較嚴格的旗標，主機名稱驗證與 CA 信任鏈驗證都維持開啟，
跟 `verify=False`（整條鏈都不驗證，CLAUDE.md 明文禁止的長期做法）是完全
不同等級的放寬。

**編碼**：回應內容含 BOM，需用 `utf-8-sig` 解碼（同 `cbc_rf_rate_client.py`
記載的央行端點共通陷阱）。

**URL 路徑編碼**：資料夾名稱「外匯局」是中文，直接寫進原始碼容易在不同
編輯器/終端機編碼下出錯，這裡用 URL-encode 過的路徑常數。
"""
from __future__ import annotations

import json
import ssl
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import yfinance as yf

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_PATH = REPO_ROOT / "data" / "fx.json"
TW_TZ = timezone(timedelta(hours=8))

# https://www.cbc.gov.tw/public/data/OpenData/外匯局/FTDOpenData015.csv
CBC_FX_URL = (
    "https://www.cbc.gov.tw/public/data/OpenData/"
    "%E5%A4%96%E5%8C%AF%E5%B1%80/FTDOpenData015.csv"
)
CBC_SOURCE_LABEL = "央行外匯局官方牌告匯率（FTDOpenData015，銀行間每日收盤即期匯率）"


class _StrictOffAdapter(requests.adapters.HTTPAdapter):
    """只關閉 `ssl.VERIFY_X509_STRICT` 這一個旗標，主機名稱驗證與 CA 信任鏈
    驗證維持開啟——見本檔 docstring「SSL 已知問題」段落，不是 `verify=False`。
    """

    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


def _fetch_cbc_fx() -> dict:
    session = requests.Session()
    session.mount("https://", _StrictOffAdapter())
    resp = session.get(CBC_FX_URL, timeout=20)
    resp.raise_for_status()
    text = resp.content.decode("utf-8-sig")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        raise RuntimeError("央行牌告匯率 CSV 內容為空")
    header = lines[0].split(",")
    if header[:2] != ["日期", "NTD/USD"]:
        raise RuntimeError(f"央行牌告匯率 CSV 表頭不符預期：{header[:2]}")
    last_date_raw, last_rate_raw = lines[-1].split(",")[:2]
    # 日期格式 YYYYMMDD（西元年，不是民國年——跟 cbc_rf_rate_client.py 的
    # A13Rate.csv 民國年月不同端點、不同格式，已實測核對此端點就是西元年）
    last_date = f"{last_date_raw[0:4]}-{last_date_raw[4:6]}-{last_date_raw[6:8]}"
    return {
        "rate": round(float(last_rate_raw), 4),
        "date": last_date,
        "source": CBC_SOURCE_LABEL,
    }


def _fetch_yfinance_fx() -> dict:
    hist = yf.Ticker("TWD=X").history(period="5d")
    if hist.empty:
        raise RuntimeError("yfinance TWD=X 回傳空資料")
    last = hist.iloc[-1]
    last_date = hist.index[-1].strftime("%Y-%m-%d")
    return {
        "rate": round(float(last["Close"]), 4),
        "date": last_date,
        "source": "yfinance TWD=X（央行端點失敗時備援）",
    }


def main():
    payload = {"fetched_at": datetime.now(timezone.utc).isoformat(), "errors": []}
    try:
        payload["usd_twd"] = _fetch_cbc_fx()
    except Exception as e:
        print(f"央行牌告匯率抓取失敗，改用 yfinance 備援：{e}")
        payload["errors"].append(f"usd_twd(cbc): {e}")
        try:
            payload["usd_twd"] = _fetch_yfinance_fx()
        except Exception as e2:
            print(f"yfinance 備援也失敗：{e2}")
            payload["errors"].append(f"usd_twd(yfinance): {e2}")
            payload["usd_twd"] = None

    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"寫入 {OUT_PATH}：{payload.get('usd_twd')}")


if __name__ == "__main__":
    main()
