"""假設#52（事件反應速度）資料源可行性查證——公開資訊觀測站（MOPS）
`t05st01`（公司當日重大訊息之詳細內容）功能，續查「窄查詢是否能拿到
不超限的完整資料表格」。

背景（見`HYPOTHESIS_QUEUE.md` #52條目「(j)路徑(b)歷史回填重大突破」段落）：
- 未帶`co_id`、月份查全月（`month=all`）→ 回應「查詢資料量過大，請縮小
  查詢範圍再次查詢」（伺服器端確實嘗試執行查詢，只是筆數超限，不是被
  安全機制封鎖）。
- 意外發現孤立探測檔`t05st02_result.html`顯示`co_id`留空時，MOPS會
  回「未指定公司代號時，僅能查詢單日重大訊息」——這暗示**不指定公司
  代號時，b_date/e_date必須限縮成同一天**（不能查全月），這是本輪要
  驗證的具體假設。

本腳本只做**單一歷史交易日**的窄查詢驗證，確認能否拿到完整（非超限
錯誤訊息）的資料表格，不做任何批次回填、不寫入正式歷史快取。

節流：MOPS非商用API，比照`mops_buyback_client.py`同一個節流精神
（`CLAUDE.md`已知地雷章節），每次呼叫間隔`SLEEP_BETWEEN_CALLS`秒。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

FORM_URL = "https://mopsov.twse.com.tw/mops/web/t05st01"
AJAX_URL = "https://mopsov.twse.com.tw/mops/web/ajax_t05st01"
HEADERS = {
    "User-Agent": "AlphaApp/0.2 (jlove201314@yahoo.com.tw)",
    "Referer": FORM_URL,
    "Origin": "https://mopsov.twse.com.tw",
    "Content-Type": "application/x-www-form-urlencoded",
}
SLEEP_BETWEEN_CALLS = 2.0
OUT_DIR = Path(__file__).parent / "data" / "mops_t05st01_probe"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _session_with_cookie() -> requests.Session:
    """先GET表單頁拿jcsession cookie，比照#52「(j)」段落記錄的成功流程。"""
    s = requests.Session()
    r = s.get(FORM_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return s


def query_single_day(s: requests.Session, roc_year: str, month: str, day: str, typek: str = "all") -> requests.Response:
    """單一交易日、全市場（不指定co_id）查詢。month/day為2位數字串（例如'09'/'08'）。"""
    payload = {
        "encodeURIComponent": "1",
        "step": "1",
        "firstin": "1",
        "off": "1",
        "keyword4": "",
        "code1": "",
        "TYPEK2": "",
        "checkbtn": "",
        "queryName": "co_id",
        "inpuType": "co_id",
        "TYPEK": typek,
        "co_id": "",
        "year": roc_year,
        "month": month,
        "b_date": day,
        "e_date": day,
    }
    resp = s.post(AJAX_URL, headers=HEADERS, data=payload, timeout=30)
    resp.raise_for_status()
    return resp


def summarize(resp: requests.Response, label: str) -> dict:
    text = resp.text
    soup = BeautifulSoup(text, "html.parser")
    tables = soup.find_all("table")
    n_rows_best = 0
    n_cols_best = 0
    for t in tables:
        trs = t.find_all("tr")
        if not trs:
            continue
        n_cols = len(trs[0].find_all(["th", "td"]))
        if n_cols > n_cols_best:
            n_cols_best = n_cols
            n_rows_best = len(trs)
    too_large = "查詢資料量過大" in text
    single_day_only = "僅能查詢單日" in text
    out_path = OUT_DIR / f"{label}.html"
    out_path.write_text(text, encoding="utf-8")
    return {
        "label": label,
        "status_code": resp.status_code,
        "n_tables": len(tables),
        "best_table_rows": n_rows_best,
        "best_table_cols": n_cols_best,
        "too_large_error": too_large,
        "single_day_only_error": single_day_only,
        "saved_to": str(out_path),
    }


def main():
    s = _session_with_cookie()
    results = []
    # 事前挑3個TRAIN期內的歷史交易日（民國年），涵蓋不同年份，避免單一
    # 日期巧合。全部是已知的一般交易日（非國定假日）。
    test_days = [
        ("104", "01", "05"),  # 2015-01-05
        ("109", "06", "15"),  # 2020-06-15
        ("113", "09", "08"),  # 2024-09-08 (VAL期最後一年附近)
    ]
    for roc_year, month, day in test_days:
        label = f"t05st01_single_{roc_year}{month}{day}"
        resp = query_single_day(s, roc_year, month, day)
        summary = summarize(resp, label)
        results.append(summary)
        print(summary)
        time.sleep(SLEEP_BETWEEN_CALLS)
    return results


if __name__ == "__main__":
    main()
