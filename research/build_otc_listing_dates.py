# -*- coding: utf-8 -*-
"""查.二第一點：TPEx（上櫃）「公司代號→上櫃日期」對照表（2026-09-27總司令
裁示【新.二結案＋紙.一＋查.二放行】放行，補`build_twse_listing_dates.py`
當初刻意排除的TPEx缺口——該檔案docstring明寫「TPEx留待有初步訊號後再視
預算擴充」，查.二的查證結果（`audit_q2_ipo_pre_listing.py`）就是這個訊號）。

**只呼叫官方API，不抓網頁**：TPEx OpenAPI `mopsfin_t187ap03_O`（上櫃公司
基本資料，免金鑰），單一請求、零重複。欄位`SecuritiesCompanyCode`/
`DateOfListing`（英文欄名，跟TWSE版`t187ap03_L`用中文欄名「公司代號」/
「上市日期」不同，本輪已用live請求逐一核對確認正確欄名，非猜測）。

輸出：`research/data/otc_listing_dates.json`（跟`twse_listing_dates.json`
同一種結構，`listing_dates`欄位語意是「上櫃日期」不是「上市日期」，欄位
名稱沿用`listing_dates`以便`universe.py`合併時共用同一套讀取邏輯，不是
命名疏忽）。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

TPEX_O_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"
OUT_PATH = Path(__file__).parent / "data" / "otc_listing_dates.json"
TW_TZ = timezone(timedelta(hours=8))


def fetch_otc_listing_dates() -> dict[str, str]:
    r = requests.get(TPEX_O_URL, timeout=40)
    r.raise_for_status()
    rows = json.loads(r.content.decode("utf-8"))
    if not isinstance(rows, list) or not rows:
        raise RuntimeError(f"TPEx mopsfin_t187ap03_O 回傳非預期格式或空列表"
                            f"（len={len(rows) if isinstance(rows, list) else 'N/A'}），"
                            "疑似端點格式變動或本輪被軟性限流回空值，不可靜默當作『查無資料』。")
    out: dict[str, str] = {}
    skipped = 0
    for row in rows:
        sid = str(row.get("SecuritiesCompanyCode") or "").strip()
        listed = str(row.get("DateOfListing") or "").strip()
        if not sid or not listed or not listed.isdigit() or len(listed) != 8:
            skipped += 1
            continue
        out[sid] = listed
    if skipped:
        print(f"  略過 {skipped}/{len(rows)} 列（公司代號或上櫃日期缺值/格式不符YYYYMMDD）")
    return out


def main() -> None:
    listing = fetch_otc_listing_dates()
    print(f"成功解析 {len(listing)} 檔TPEx現存上櫃公司上櫃日期")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "generated_at": datetime.now(TW_TZ).isoformat(),
        "source": TPEX_O_URL,
        "scope": "TPEx現存上櫃公司（不含TWSE上市、不含興櫃、不含已下市公司——"
                 "興櫃股依裁示直接從嚴格宇宙排除，不需要它的日期）",
        "n_companies": len(listing),
        "listing_dates": listing,
    }
    OUT_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已寫入 {OUT_PATH}（{len(listing)}檔）")


if __name__ == "__main__":
    main()
