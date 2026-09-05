"""#41 內部人持股轉讓地基查證探測腳本（2026-09-06 hypothesis_queue排程接續）。

用途：確認MOPS互動查詢頁「董事、監察人、經理人及大股東持股餘額」查詢頁的
正確功能代碼與POST參數，證明可以查詢任意歷史年月（民國yyy+mm），不像
openapi t187ap11/12/13只給最新單一快照。

確認結果（本輪已用requests實測通過）：
- 產業別彙總清單頁：GET https://mopsov.twse.com.tw/mops/web/stapap1_all
  → POST https://mopsov.twse.com.tw/mops/web/ajax_stapap1_all
    參數：sTYPEK(sii/otc/rotc/pub)、TYPEK(同sTYPEK)、firstin='true'、
    step='1'、kind=''、id=''、skind(產業代碼，見下方SKIND_OPTIONS)、
    YM(民國年+兩位月，例如11407=民國114年7月)
  → 回傳該產業當月的公司代號/簡稱清單（不含實際持股數字）。
- 個股明細頁：GET https://mopsov.twse.com.tw/mops/web/stapap1
  → POST https://mopsov.twse.com.tw/mops/web/ajax_stapap1
    參數：firstin='true'、colorchg=''、year(民國年三碼)、month(兩位數)、
    co_id(股票代號)、TYPEK(sii/otc)、step='0'
  → 回傳該公司該月「職稱/姓名/選任時持股/目前持股/設質股數/設質比率/
    配偶未成年子女持股/利用他人名義持股」逐筆明細（HTML表格，Big5編碼
    但requests用utf-8 decode出來是亂碼，需用.content配合正確編碼或直接
    用latin1→big5轉換，正式回補腳本要處理編碼問題，本探測腳本未處理，
    只驗證流程可行）。

**重大結論**：跟上一輪（2026-09-06T07:28）記錄的「地基查證卡住待下一輪」
不同——本輪找到MOPS官方文件內建連結（stapap1_all → 詳細資料按鈕 →
stapap1），確認**歷史查詢完全可行**，不是openapi那種只給最新快照的死路。
但代價是**per-company查詢**（不像#40買回股份`t35sc09`是全市場單一
date-range查詢），全市場約1700+檔股票×多年月頻率，全歷史回補請求量
會很大，需要下一輪設計節流/取樣頻率（例如改用季度而非月度、或先用
較小樣本先驗第1關cheap gate，比照#40先用抽樣100檔驗證機制、確認有
訊號再考慮全量回補的做法）。

本探測腳本僅做3檔公司(2330/1101/2317)x單一月份(11306)的連通性測試，
每次請求間隔1.5秒（避免撞到TWSE/MOPS節流，比照CLAUDE.md已知地雷章節
提醒），**未執行任何正式回補**，不產生任何`data/`快取檔案。
"""
import time

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Referer": "https://mopsov.twse.com.tw/mops/web/stapap1",
    "Origin": "https://mopsov.twse.com.tw",
    "Content-Type": "application/x-www-form-urlencoded",
}

DETAIL_URL = "https://mopsov.twse.com.tw/mops/web/ajax_stapap1"
LIST_URL = "https://mopsov.twse.com.tw/mops/web/ajax_stapap1_all"


def fetch_company_month(co_id: str, year_roc: str, month: str, typek: str = "sii") -> str:
    """查詢單一公司單一民國年月的董監持股明細（回傳原始HTML）。"""
    data = {
        "firstin": "true",
        "colorchg": "",
        "year": year_roc,
        "month": month,
        "co_id": co_id,
        "TYPEK": typek,
        "step": "0",
    }
    resp = requests.post(DETAIL_URL, headers=HEADERS, data=data, timeout=20)
    resp.raise_for_status()
    return resp.content.decode("utf-8", errors="ignore")


def fetch_industry_month_company_list(skind: str, year_month_roc: str, market: str = "sii") -> str:
    """查詢單一產業單一民國年月的公司清單（回傳原始HTML，僅公司代號/簡稱，無持股數字）。"""
    data = {
        "sTYPEK": market,
        "TYPEK": market,
        "firstin": "true",
        "step": "1",
        "kind": "",
        "id": "",
        "skind": skind,
        "YM": year_month_roc,
    }
    resp = requests.post(LIST_URL, headers=HEADERS, data=data, timeout=20)
    resp.raise_for_status()
    return resp.content.decode("utf-8", errors="ignore")


if __name__ == "__main__":
    test_ids = ["2330", "1101", "2317"]
    for cid in test_ids:
        html = fetch_company_month(cid, "113", "06")
        ok = "div01" in html and len(html) > 3000
        print(cid, len(html), "OK" if ok else "EMPTY/SHORT")
        time.sleep(1.5)
