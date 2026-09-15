# -*- coding: utf-8 -*-
"""每日排程更新 data/short_lending_available.json（上市上櫃股票當日可借券賣出股數）。

`PENDING_QUEUE.md`「源頭二.3」第5名候選原始標籤是「借券賣出餘額」，但實測
唯一可程式存取、TWSE openapi swagger目錄裡含「借券」關鍵字的端點只有
`SBL/TWT96U`，其官方欄位定義是**「當日可借券賣出股數」（借券供給水位／庫存量）**，
語意跟「借券賣出餘額」（已借券賣出、尚未回補的未平倉部位）**不是同一件事**——
`docs/FIRST_HAND_SOURCES.md` #5 先前查證已記錄「是餘量非成交費率」，本次
接入前又更進一步確認：是「可借額度」，不是「已借部位」，也不是「借券費率」。
誠實只接入這一個真實存在的端點，不誇大成原始標籤講的那個概念。

端點（TWSE官方openapi，免金鑰）：
https://openapi.twse.com.tw/v1/SBL/TWT96U

**已知地雷（2026-09-15實測發現，寫死避免重踩）**：這個端點回傳的1237列，
每一列同時有`TWSECode`/`TWSEAvailableVolume`（上市）與`GRETAICode`/
`GRETAIAvailableVolume`（上櫃）四個欄位，**但同一列的上市代號跟上櫃代號
完全不是同一家公司**（例如某列`TWSECode=00400A`卻`GRETAICode=00411A`）。
這是把「上市清單」與「上櫃清單」兩個長度不同的獨立陣列用位置（index）
硬湊成同一列JSON，不是關聯式資料——**絕對不能把同一列的上市/上櫃當同一檔
股票處理**。正確做法是拆成兩個獨立清單：`TWSECode`不為空的視為上市清單、
`GRETAICode`不為`_`且不為空的視為上櫃清單，兩者互不對應。

**誠實限制**：這個端點只有「當日可借券賣出股數」，沒有借券費率（各券商
議定，無公開統一費率）、沒有已借券賣出的未平倉部位（TWSE未公開此細項）。
CLAUDE.md「借券成本與可借量硬規則」提到的兩項缺口（成本／可借量）本項
只能補上「可借量」的其中一部分（供給水位而非即時可借與否），成本部分
仍待採購或另尋來源，不得因為接入這個端點就宣稱借券成本問題已解決。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_PATH = REPO_ROOT / "data" / "short_lending_available.json"
URL = "https://openapi.twse.com.tw/v1/SBL/TWT96U"
HEADERS = {"User-Agent": "AlphaApp-ShortLendingAvailable contact@alpha-app-project.example"}


def _to_int(s):
    if not s or s in ("_", "-"):
        return None
    try:
        return int(str(s).replace(",", ""))
    except ValueError:
        return None


def main() -> int:
    r = requests.get(URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    rows = r.json()
    if not isinstance(rows, list) or not rows:
        print(f"錯誤：{URL} 回傳非預期格式或空陣列（可能是openapi.twse.com.tw對無效路徑回200+HTML的已知地雷，需人工核對）")
        return 1

    twse: dict[str, int] = {}
    otc: dict[str, int] = {}
    for row in rows:
        tw_code = row.get("TWSECode")
        tw_vol = _to_int(row.get("TWSEAvailableVolume"))
        if tw_code and tw_vol is not None:
            twse[tw_code] = tw_vol
        otc_code = row.get("GRETAICode")
        otc_vol = _to_int(row.get("GRETAIAvailableVolume"))
        if otc_code and otc_code != "_" and otc_vol is not None:
            otc[otc_code] = otc_vol

    out = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "TWSE官方openapi SBL/TWT96U「上市上櫃股票當日可借券賣出股數」，免金鑰",
        "url": URL,
        "note": "僅「可借券賣出股數」（借券供給水位），非借券費率、非已借券賣出的未平倉部位；twse/otc為兩個獨立清單，不可跨清單用同一列對應",
        "twse": twse,
        "otc": otc,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    print(f"寫入 {OUT_PATH}，上市 {len(twse)} 檔、上櫃 {len(otc)} 檔")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
