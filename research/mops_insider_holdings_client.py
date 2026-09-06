"""`HYPOTHESIS_QUEUE.md` #41（內部人董監持股轉讓）資料源客戶端——公開資訊觀測站
（MOPS）互動查詢頁功能代碼`stapap1`（董事、監察人、經理人及大股東持股餘額）。

跟`mops_buyback_client.py`（#40）同一種「可重複呼叫、per-筆快取檔案本身就是
完成紀錄」設計，但這裡是**per-company per-month**查詢（不像`t35sc09`能一次
查全市場某個日期範圍），所以快取粒度是(stock_id, typek, year_roc, month)
一列一個parquet檔，backfill腳本可以中斷後重跑接續、不會重打已快取的組合。

查證結果（`mops_insider_holdings_probe.py`兩輪 + 本輪`hypothesis_queue`排程
實測確認）：
- 端點：`POST https://mopsov.twse.com.tw/mops/web/ajax_stapap1`
  參數：`firstin='true'`、`colorchg=''`、`year`(民國年三碼)、`month`(兩位數)、
  `co_id`(股票代號)、`TYPEK`('sii'上市/'otc'上櫃)、`step='0'`。
- **編碼**：`resp.content.decode('utf-8')`本輪實測乾淨可讀（中文姓名/職稱皆
  正確），先前探測腳本文件裡「utf-8解出來是亂碼」的疑慮已排除——那是終端機
  顯示層問題，不是實際解碼問題（本輪用寫檔+`Read`工具驗證過)。
- **本輪只抓「全體董監持股合計」單一彙總數字**（不逐一加總40+筆個別董監事/
  經理人明細列）：頁面本身有一張獨立的彙總小表（非獨立董事/獨立董事/非獨立
  監察人/獨立監察人/非獨立董監/獨立董監/**全體董監**持股合計共7列），直接
  取「全體董監持股合計」那一列比自己加總逐筆明細列更穩健（不受個別列數量
  在不同公司/月份間變動影響），代價是只捕捉「董監事」這個子集、還沒涵蓋
  經理人與大股東（>10%）——這是刻意的第一版簡化，見`HYPOTHESIS_QUEUE.md`
  #41條目「資料可行性查證」小節，若第1關pilot顯示有訊號，未來輪可以再擴充
  到逐筆經理人/大股東明細。

**節流**：MOPS非商用API，比照`mops_buyback_client.py`同一個節流精神
（`CLAUDE.md`已知地雷章節），每筆請求間隔`SLEEP_BETWEEN_CALLS`秒。

2026-09-06 hypothesis_queue排程接續（#41第1關地基建置，本輪）。
"""
from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

DATA_DIR = Path(__file__).parent / "data" / "raw_mops_insider"
DATA_DIR.mkdir(parents=True, exist_ok=True)

URL = "https://mopsov.twse.com.tw/mops/web/ajax_stapap1"
REFERER = "https://mopsov.twse.com.tw/mops/web/stapap1"
HEADERS = {
    "User-Agent": "AlphaApp/0.2 (jlove201314@yahoo.com.tw)",
    "Referer": REFERER,
    "Origin": "https://mopsov.twse.com.tw",
    "Content-Type": "application/x-www-form-urlencoded",
}
SLEEP_BETWEEN_CALLS = 1.8
MAX_RETRIES = 3

TOTAL_ROW_LABEL = "全體董監持股合計"


def _cache_path(stock_id: str, year_roc: str, month: str, typek: str) -> Path:
    return DATA_DIR / f"INSIDER_{stock_id}_{typek}_{year_roc}{month}.parquet"


def _fetch_html(co_id: str, year_roc: str, month: str, typek: str) -> str:
    payload = {
        "firstin": "true",
        "colorchg": "",
        "year": year_roc,
        "month": month,
        "co_id": co_id,
        "TYPEK": typek,
        "step": "0",
    }
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.post(URL, headers=HEADERS, data=payload, timeout=20)
            r.raise_for_status()
            return r.content.decode("utf-8", errors="ignore")
        except Exception as e:  # noqa: BLE001 -- 資料源禮儀：重試+backoff，不靜默吞錯
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(
        f"MOPS stapap1 fetch失敗 co_id={co_id} {year_roc}{month} typek={typek}: {last_err}"
    )


def _parse_board_holdings_total(html: str) -> float | None:
    """找所有table裡列首欄=='全體董監持股合計'的那一列，回傳第2欄數字
    （逗號千分位股數轉float）。查無此列（例如該公司該月沒有申報資料）
    回傳None——這是設計上的『查無資料』信號，呼叫端`fetch_and_cache()`
    會把它記進`status`欄位，不是靜默吞錯。"""
    try:
        soup = BeautifulSoup(html, "html.parser")
        for table in soup.find_all("table"):
            for tr in table.find_all("tr"):
                cells = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
                if cells and cells[0] == TOTAL_ROW_LABEL and len(cells) >= 2:
                    raw = cells[1].replace(",", "")
                    return float(raw)
    except Exception:
        return None
    return None


def fetch_and_cache(stock_id: str, year_roc: str, month: str, typek: str = "sii", force: bool = False) -> dict:
    """回傳一列dict：stock_id/year_roc/month/typek/board_holdings_total(可能
    None)/status('cached'|'fetched_ok'|'fetched_empty'|'error')。快取命中
    （parquet已存在）就不重打，可安全重跑backfill腳本接續。"""
    path = _cache_path(stock_id, year_roc, month, typek)
    if path.exists() and not force:
        row = pd.read_parquet(path).iloc[0].to_dict()
        row["status"] = "cached"
        return row

    total: float | None
    try:
        html = _fetch_html(stock_id, year_roc, month, typek)
        total = _parse_board_holdings_total(html)
        status = "fetched_ok" if total is not None else "fetched_empty"
    except Exception as e:  # noqa: BLE001 -- 記錄後繼續，不中斷整條backfill迴圈
        print(f"  [WARN] insider fetch失敗 {stock_id} {year_roc}{month} {typek}: {e}")
        total = None
        status = "error"

    row = {
        "stock_id": stock_id,
        "year_roc": year_roc,
        "month": month,
        "typek": typek,
        "board_holdings_total": total,
    }
    pd.DataFrame([row]).to_parquet(path, index=False)
    time.sleep(SLEEP_BETWEEN_CALLS)
    out = dict(row)
    out["status"] = status
    return out


def load_all_cached() -> pd.DataFrame:
    """把`DATA_DIR`底下所有已快取的parquet讀進來合併成一份，不去重（每個
    檔案本身就是唯一的(stock_id,typek,year_roc,month)組合，天然無重複）。"""
    files = sorted(DATA_DIR.glob("INSIDER_*.parquet"))
    if not files:
        return pd.DataFrame()
    frames = [pd.read_parquet(f) for f in files]
    df = pd.concat(frames, ignore_index=True)
    return df.reset_index(drop=True)


if __name__ == "__main__":
    r = fetch_and_cache("2330", "109", "03", "sii")
    print(r)
