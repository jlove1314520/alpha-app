"""一次性建置 data/company_info.json（代號→公司名稱→產業分類），2026-08-27。

背景：使用者P1抽查發現 `generate_scores_live.py` 的選股結果裡，多數股票的
`name`/`industry` 欄位是null——原本`_name_map()`只讀`quotes_tw.json`（只有
使用者自選股當下報價，不是全市場），且`industry`欄位這支腳本一直都寫死None
（檔頭已誠實揭露「JSON-only路徑沒有產業對照表來源」）。

這裡用同一套「讀research端FinMind本機快取，一次性建成committed JSON」模式
（跟`build_fundamentals_json.py`/`build_price_history.py`同一個解法）：讀
`TaiwanStockInfo`快取（涵蓋全市場，包含代號/名稱/產業分類），整理成
`data/company_info.json`，供`generate_scores_live.py`讀取（不影響
`quotes_tw.json`原本自選股報價用途，兩者並存）。

**這是相對靜態的參考資料**（公司名稱/產業分類不常變動），不需要每日排程，
之後有新股上市/更名時，重跑這支腳本一次即可（merge-safe，只新增/更新，
不刪除既有代號）。
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).parent / "data" / "raw"
OUT_PATH = Path(__file__).parent.parent / "data" / "company_info.json"


def main():
    candidates = sorted(RAW_DIR.glob("TaiwanStockInfo__*.parquet"))
    if not candidates:
        raise RuntimeError(f"{RAW_DIR} 底下找不到TaiwanStockInfo快取，無法建置company_info.json")

    frames = [pd.read_parquet(p) for p in candidates]
    info = pd.concat(frames, ignore_index=True)

    # 2026-08-27發現的真bug（使用者P1抽查引出）：FinMind的TaiwanStockInfo快取
    # 對同一檔股票、同一天，有時會有兩筆「不同產業分類」的紀錄（實測：華邦電
    # 2344在2026-08-22這天同時有"半導體業"跟"電子工業"兩種分類），不是單純的
    # 歷史沿革（那種情況date不同，排序取最新即可解決，這裡先做）——約24%的
    # 4位數股票代碼有這種同日期歧義。與其隨便挑一個可能是錯的塞給使用者，
    # 這裡誠實處理：先按date排序取每檔最新日期的紀錄，同一天仍有多種分類的
    # 話，industry回傳None（寧可顯示「—」也不要顯示錯的產業分類），只有
    # name這種沒有觀察到歧義問題的欄位正常取值。
    info = info.sort_values("date")
    name_map = info.drop_duplicates(subset=["stock_id"], keep="last").set_index("stock_id")["stock_name"]

    latest_date = info.groupby("stock_id")["date"].transform("max")
    latest_rows = info[info["date"] == latest_date]
    industry_counts = latest_rows.groupby("stock_id")["industry_category"].nunique()
    unambiguous_codes = industry_counts[industry_counts == 1].index
    industry_map = (
        latest_rows[latest_rows["stock_id"].isin(unambiguous_codes)]
        .drop_duplicates(subset=["stock_id"])
        .set_index("stock_id")["industry_category"]
    )
    ambiguous_count = int((industry_counts > 1).sum())

    companies = {}
    if OUT_PATH.exists():
        try:
            companies = json.loads(OUT_PATH.read_text(encoding="utf-8")).get("companies", {})
        except Exception:
            companies = {}
    prior_count = len(companies)

    for code in name_map.index:
        companies[code] = {
            "name": name_map.get(code),
            "industry": industry_map.get(code),
        }

    new_count = len(companies)
    if new_count < prior_count:
        raise RuntimeError(
            f"覆蓋率不應該在merge之後下降，但從 {prior_count} 變成 {new_count}——"
            "已中止寫入，不要用這份結果覆蓋既有檔案。"
        )

    payload = {
        "meta": {
            "source": "FinMind TaiwanStockInfo（research端本機parquet快取整理，一次性/不常變動）",
            "note": "供generate_scores_live.py顯示公司名稱/產業分類用，跟quotes_tw.json"
                    "（僅自選股當下報價）用途不同、互不影響。",
            "industry_ambiguous_count": ambiguous_count,
            "industry_ambiguous_note": (
                f"{ambiguous_count}檔股票在FinMind快取裡同一天有超過一種產業分類"
                "（原始資料本身的歧義，不是這支腳本的bug），這些股票的industry"
                "誠實留None，不猜一個可能錯的分類；name欄位沒有觀察到這個問題。"
            ),
        },
        "companies": companies,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"寫入 {OUT_PATH}，{new_count} 檔公司名稱/產業對照（merge前既有 {prior_count} 檔，"
          f"{ambiguous_count}檔產業分類有歧義故留None）")


if __name__ == "__main__":
    main()
