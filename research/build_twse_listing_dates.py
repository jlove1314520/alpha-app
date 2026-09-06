# -*- coding: utf-8 -*-
"""`HYPOTHESIS_QUEUE.md` #46（新股上市長期弱勢）地基腳本：抓取並存檔TWSE
`t187ap03_L`（上市公司基本資料）的「公司代號→上市日期」對照表。

**只做TWSE、只做現存公司**——依#46條目已寫明的範圍界定決策：TPEx下市清單
三方查證後確認查無官方API（見`HYPOTHESIS_QUEUE.md`#46「(b)」段落），
下市公司清單（`suspendListingCsvAndHtml`）沒有上市日期欄位需額外拼接，
本輪先只用「現存TWSE上市公司」子樣本做cheap gate，TPEx留待有初步訊號後
再視預算擴充，這是誠實揭露的存活者偏差局限，不是忽略。

單一API呼叫、零金鑰、複用既有`requests`直接抓取模式（跟
`backfill_company_industry.py::twse_code_map()`同一個端點/同一種
requests.get寫法，只是這裡只取兩個欄位）。

輸出：`research/data/twse_listing_dates.json`
  {"公司代號": "YYYYMMDD上市日期", ...}（只含成功解析出兩個欄位的列）

2026-09-06 hypothesis_queue排程接續，#46「下一輪待辦」第2點。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

TWSE_LIST_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
OUT_PATH = Path(__file__).parent / "data" / "twse_listing_dates.json"
TW_TZ = timezone(timedelta(hours=8))


def fetch_listing_dates() -> dict[str, str]:
    r = requests.get(TWSE_LIST_URL, timeout=40)
    r.raise_for_status()
    rows = json.loads(r.content.decode("utf-8"))  # 明確用utf-8解bytes，別信requests猜的編碼
    if not isinstance(rows, list) or not rows:
        raise RuntimeError(f"TWSE t187ap03_L 回傳非預期格式或空列表（len={len(rows) if isinstance(rows, list) else 'N/A'}），"
                            "疑似端點格式變動或本輪被軟性限流回空值，不可靜默當作『查無資料』。")
    out: dict[str, str] = {}
    skipped = 0
    for row in rows:
        sid = str(row.get("公司代號") or "").strip()
        listed = str(row.get("上市日期") or "").strip()
        if not sid or not listed or not listed.isdigit() or len(listed) != 8:
            skipped += 1
            continue
        out[sid] = listed
    if skipped:
        print(f"  略過 {skipped}/{len(rows)} 列（公司代號或上市日期缺值/格式不符YYYYMMDD）")
    return out


def main() -> None:
    listing = fetch_listing_dates()
    print(f"成功解析 {len(listing)}/{len(listing)} 檔TWSE現存上市公司上市日期"
          f"（總筆數見上方略過統計）")
    # sanity：跟已知案例台泥(1101)交叉核對（HYPOTHESIS_QUEUE.md #46經濟理由段落提過的範例）
    assert listing.get("1101") == "19620209", (
        f"sanity失敗：1101(台泥)上市日期應為19620209，實得{listing.get('1101')!r}，"
        "疑似欄位對錯或端點格式變動，不可靜默繼續。")
    print("sanity通過：1101(台泥)上市日期=19620209，跟已知官方數字一致")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "generated_at": datetime.now(TW_TZ).isoformat(),
        "source": TWSE_LIST_URL,
        "scope": "TWSE現存上市公司（不含TPEx上櫃、不含已下市公司，見HYPOTHESIS_QUEUE.md#46範圍界定決策）",
        "n_companies": len(listing),
        "listing_dates": listing,
    }
    OUT_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已寫入 {OUT_PATH}（{len(listing)}檔）")


if __name__ == "__main__":
    main()
