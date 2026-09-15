"""Probe：假設#72（重大訊息公告類型事件研究——聚焦「重大訂單/得標」子類別）
的地基查證。

背景：`PENDING_QUEUE.md`「研究.a」總司令原始指令是「用MOPS既有管線資料」
（即`.github/scripts/fetch_news_events.py`用的`openapi.twse.com.tw/v1/
opendata/t187ap04_L`）。本輪查證發現：**這個既有管線只回傳當日快照，
沒有日期區間查詢參數**（本機實測82筆全部同一天）——跟`#71`（減資假設）
2026-09-10已獨立查證出的結論完全一致（見`HYPOTHESIS_QUEUE.md`#71條目
「(1) MOPS官方『減資彙總查詢』頁面」段落）。`data/events.json`本身能
累積出90天視窗只是因為排程每天疊加存檔（`keep_days=90`，2026-09-08才
開始建置），不是端點本身可以回溯查詢，離2015-2024（TRAIN/VAL邊界）
還差得遠——依`GATE_SEQUENCE`前置的「資料源歷史起點探測」判準，這條路
不可行。

本輪改用WebSearch三來源查證找到MOPS互動查詢頁`t51sb10`（重大訊息主旨
全文檢索），確認：
1. **官方頁面本身**——`mopsov.twse.com.tw/mops/web/t51sb10_q1`是真實
   表單頁（非SPA殼頁），欄位含`KIND`（L=上市/O=上櫃/R=興櫃/C=公開發行）、
   `keyWord`（關鍵字，可留空＝全部）、`year`（民國年）、`month1`
   （0=全年度或1-12）、`begin_day`/`end_day`、`Orderby`，送到
   `ajax_t51sb10`。
2. **本機實測**（本檔案）——`KIND=L`、`keyWord=''`、`year=104`
   （民國104=2015）、`month1=0`：回傳全市場全年度重大訊息列表，
   分頁顯示最後一頁是**第2045頁**（預設15筆/頁），證實歷史至少回溯
   到2015年，滿足GATE_SEQUENCE「起點早於train/val邊界」門檻，但也
   代表無關鍵字的全量掃描量體極大（單一市場單一年度約3萬筆），不是
   一輪能做完的全量回補。
3. **關鍵字篩選可行**——`keyWord='得標'`同一年度查詢只回15筆（未見
   分頁按鈕，代表≤15筆），且內容確實是「公告本公司得標工程」這類
   契約得標公告，證實關鍵字篩選有效縮小量體，適合用來對單一子類別
   （重大訂單/得標）做經濟合理的節流回補，不需要掃描全市場全部類型
   訊息。

**本輪只做地基查證，不做全歷史回補**（比照`buyback_announcement_probe.py`
先例，回補腳本留給下一輪，一輪一個有界工作單位）。

資料源禮儀：MOPS非商用API，逐筆查詢間隔加延遲（`CLAUDE.md`已知地雷章節精神）。
"""
from __future__ import annotations

import time

import requests

URL = "https://mopsov.twse.com.tw/mops/web/ajax_t51sb10"
REFERER = "https://mopsov.twse.com.tw/mops/web/t51sb10_q1"
HEADERS = {
    "User-Agent": "AlphaApp/0.2 (jlove201314@yahoo.com.tw)",
    "Referer": REFERER,
}

# 民國年份：104(2015) 測試最早年份是否有資料；114(2025) 對照組（已知可行）
PROBE_YEARS = ["104", "114"]
KEYWORD = "得標"  # 對應classify()既有「重大訂單」分類規則之一（接單|訂單|得標|簽約|合作備忘）


def query(kind: str, keyword: str, year: str) -> str:
    payload = {
        "step": "1", "firstin": "true", "id": "", "key": "", "TYPEK": "", "Stp": "4", "go": "false",
        "r1": "1", "KIND": kind, "CODE": "", "keyWord": keyword, "Condition2": "1", "keyWord2": "",
        "year": year, "month1": "0", "begin_day": "1", "end_day": "31", "Orderby": "1",
    }
    r = requests.post(URL, headers=HEADERS, data=payload, timeout=30)
    r.raise_for_status()
    return r.text


def count_rows_and_pages(html: str) -> tuple[int, int]:
    rows = html.count("<TR class=")
    # 分頁按鈕的最後一個數字連結＝總頁數；找不到分頁按鈕代表只有1頁
    import re
    nums = re.findall(r"pagenum\.value='(\d+)'", html)
    last_page = max((int(n) for n in nums), default=1)
    return rows, last_page


def probe_one(kind: str, keyword: str, year: str, label: str) -> None:
    print(f"\n=== KIND={kind} keyWord='{keyword}' year={year} ({label}) ===")
    try:
        html = query(kind, keyword, year)
    except Exception as e:  # noqa: BLE001 -- 探查階段要看到每一種失敗模式
        print(f"FAILED (fetch): {type(e).__name__}: {e}")
        return
    print(f"html length: {len(html)}")
    if "查無資料" in html:
        print("查無資料")
        return
    rows, last_page = count_rows_and_pages(html)
    print(f"本頁列數: {rows}，總頁數: {last_page}（每頁預設15筆，粗估總筆數約 {rows if last_page <= 1 else last_page * 15}）")


def main() -> None:
    for year in PROBE_YEARS:
        # 無關鍵字：確認歷史深度與量體
        probe_one("L", "", year, "全量掃描（上市，不限關鍵字）")
        time.sleep(2.0)
        # 關鍵字篩選：確認可行的節流路徑
        probe_one("L", KEYWORD, year, f"關鍵字篩選（上市，keyWord={KEYWORD}）")
        time.sleep(2.0)


if __name__ == "__main__":
    main()
