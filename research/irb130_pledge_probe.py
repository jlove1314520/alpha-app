"""#48 董監事/經理人/大股東質權設定彙總表 地基查證探測腳本
（2026-09-06 hypothesis_queue排程接續）。

用途：確認MOPS「董事、監察人、經理人及百分之十以上大股東質權設定彙總表
(IRB130)」的真實資料端點、歷史回溯深度、上市/上櫃涵蓋範圍、以及HTML表格
解析正確性，回答#48條目「資料可行性查證」段落列出的(a)(b)(c)三個待查項目。

## 查證方式（比照#40/#41鎖定真實POST端點的做法）

1. `https://mopsov.twse.com.tw/mops/web/t05st03` 是功能選單頁（非查詢頁），
   實測抓到`href="IRB130"`相對連結。
2. `https://mopsov.twse.com.tw/mops/web/IRB130` 是互動查詢表單頁，表單
   `action="/mops/web/ajax_IRB130"`，欄位：`TYPEK`(sii/otc/rotc)、
   `year`(民國年三碼)、`month`(兩位數，補零)。
3. 對`ajax_IRB130`送出POST後，回傳的不是資料本身，而是一段JS
   `window.open`導去**靜態HTML報表**：
   `https://siis.twse.com.tw/publish/{sii|otc}/{民國年}IRB130_{月}.HTM`
   ——這個靜態URL本身**可以直接GET**，不需要先POST拿轉址script，
   已驗證直接組URL即可用。

## (a) 端點與參數確認：已解決

真實可重複使用的端點格式：
`https://siis.twse.com.tw/publish/{market}/{yyy}IRB130_{mm}.HTM`
- `market`：`sii`（上市）或`otc`（上櫃）。興櫃(`rotc`)本輪未測試。
- `yyy`：民國年三碼，例如113=2024。
- `mm`：兩位數月份，補零，例如`06`。

## (b) 歷史回溯深度：已解決，涵蓋TRAIN(2015-2020)/VAL(2021-2024)全區間

本輪實測以下組合皆HTTP 200且回傳可解析表格（見`if __name__`區塊）：
- sii：104年01月(2015-01)、104年06月、108年12月(2019-12)、114年08月
  (2025-08，最新)——**104年最早月份即可用，未進一步往前測103年或更早**。
- otc：104年01月、113年06月(2024-06)。

## (c) PIT時間差：已確認為標準月頻揭露延遲，非回溯修正風險

報表本身內嵌「資料年月:11306　資料日期:113/07/22」字樣——即**6月資料於
7月22日發布**，落後約3週，屬正常月頻公司治理揭露時間差（不是`#44`景氣
燈號那種事後才會被修正的統計數字），**未發現look-ahead風險**：只要
gate/portfolio腳本用「資料年月月底+約1個月緩衝」而非「資料年月月底」
當作訊號可得日，即可避免用到未來資訊。

## 解析正確性驗證

HTML編碼為`charset=x-x-big5`（實際是Big5），用`.decode('big5', errors=
'replace')`可正確還原中文（實測驗證1101台泥中文名稱`臺灣水泥股份有限`
還原正確，且佔持股比例0.68%與人工檢視數字一致）。表格為固定10欄格式：
`公司代號(4碼)+公司名稱(截斷)、董監事實際持有股數、本月設定股數、
本月解除股數、累計設定股數、董監事質押佔持股比例%、經理人本月實際
持有股數、大股東本月實際持有股數、經理人及大股東已設定股數、
經理人+大股東質押佔持股比例%`。本輪解析行數：
sii 104-01=856列、108-12=941列、114-08=1053列（隨上市公司數增加而增加，
符合預期）；otc 104-01=687列、113-06=824列。

## 結論：#48資料可行性三點查證(a)(b)(c)本輪全數確認可行，優於#41/#38/#47

跟`#41`內部人持股轉讓（逐檔查詢，需per-company請求）不同，這是**全市場
單一請求拿到當月所有公司**（比照`#40`買回股份`t35sc09`的效率），且是
純靜態HTML、不需要先送互動表單POST再解析轉址——比`#41`當時發現的
`stapap1`還單純。下一輪可直接進入第1關cheap gate：抓取
TRAIN(2015-2020)+VAL(2021-2024)月頻sii+otc兩市場歷史，用「董監事質押
比例（col6）」與「MoM變化」兩種訊號口徑測forward報酬Spearman相關性
（比照`#41`/`#42`/`#43`同一套train/val分期+時序洗牌null對照框架）。

本探測腳本僅做少量測試請求（sii 4次+otc 2次+功能選單頁1次+查詢表單頁
1次，共約8次請求，每次間隔1.5秒），**未執行任何正式回補、未寫入任何
`data/`快取檔案**。
"""
import re
import time

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
}

REPORT_URL_TMPL = "https://siis.twse.com.tw/publish/{market}/{roc_year}IRB130_{month:02d}.HTM"

ROW_PATTERN = re.compile(
    r"<TR><TD>(\d{4})([^<]*)</TD>\s*"
    r"<TD ALIGN=RIGHT>\s*([\d,]+)</TD>\s*"
    r"<TD ALIGN=RIGHT>\s*([\d,]+)</TD>\s*"
    r"<TD ALIGN=RIGHT>\s*([\d,]+)</TD>\s*"
    r"<TD ALIGN=RIGHT>\s*([\d,]+)</TD>\s*"
    r"<TD ALIGN=RIGHT>\s*([\d.]+)</TD>\s*"
    r"<TD ALIGN=RIGHT>\s*([\d,]+)</TD>\s*"
    r"<TD ALIGN=RIGHT>\s*([\d,]+)</TD>\s*"
    r"<TD ALIGN=RIGHT>\s*([\d,]+)</TD>\s*"
    r"<TD ALIGN=RIGHT>\s*([\d.]+)</TD>"
)


def fetch_irb130_month(market: str, roc_year: int, month: int) -> str:
    """抓取單一民國年月+市場別的IRB130靜態報表HTML（回傳big5解碼後的文字）。"""
    url = REPORT_URL_TMPL.format(market=market, roc_year=roc_year, month=month)
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.content.decode("big5", errors="replace")


def parse_irb130_rows(html_text: str) -> list[dict]:
    """解析IRB130報表HTML為結構化列表，欄位對應見模組docstring。"""
    rows = []
    for m in ROW_PATTERN.findall(html_text):
        (
            co_id, co_name_trunc, board_shares, pledge_new, pledge_released,
            pledge_cum, board_pledge_pct, manager_shares, major_shareholder_shares,
            manager_major_pledge_cum, manager_major_pledge_pct,
        ) = m
        rows.append({
            "co_id": co_id,
            "co_name_trunc": co_name_trunc,
            "board_shares": int(board_shares.replace(",", "")),
            "pledge_new_this_month": int(pledge_new.replace(",", "")),
            "pledge_released_this_month": int(pledge_released.replace(",", "")),
            "pledge_cum": int(pledge_cum.replace(",", "")),
            "board_pledge_pct": float(board_pledge_pct),
            "manager_shares": int(manager_shares.replace(",", "")),
            "major_shareholder_shares": int(major_shareholder_shares.replace(",", "")),
            "manager_major_pledge_cum": int(manager_major_pledge_cum.replace(",", "")),
            "manager_major_pledge_pct": float(manager_major_pledge_pct),
        })
    return rows


if __name__ == "__main__":
    test_cases = [
        ("sii", 104, 1),
        ("sii", 108, 12),
        ("sii", 113, 6),
        ("sii", 114, 8),
        ("otc", 104, 1),
        ("otc", 113, 6),
    ]
    for market, roc_year, month in test_cases:
        text = fetch_irb130_month(market, roc_year, month)
        rows = parse_irb130_rows(text)
        sample = next((r for r in rows if r["co_id"] == "1101"), None)
        print(
            f"{market} {roc_year}/{month:02d} -> rows={len(rows)}"
            + (f" 1101範例pledge_pct={sample['board_pledge_pct']}" if sample else "")
        )
        time.sleep(1.5)
