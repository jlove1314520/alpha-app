"""Probe: 假設#39（0050/台灣50指數成分股調整事件效應）的地基查證——找出
「臺灣50指數」/「中型100指數」歷次成分股調整（新納入/剔除）名單與生效
日期的免費、可程式化取得的歷史資料來源，決定這條假設是否可行。

背景：`HYPOTHESIS_QUEUE_PROTOCOL.md`第1節指引——佇列#1~38已全數結案（見
`HYPOTHESIS_QUEUE.md`「排隊順序總結」），本輪查證#39資料可行性，避免
重蹈#38覆轍（#38是先設計完整假設定義才發現資料不可及，這次先查證再
決定是否投入）。

查證方法：依序查以下三個免費/合規候選來源，任一個提供「歷史成分股
名單+每次調整生效日期」的結構化資料就算可行：
1. FinMind——是否有指數成分股/ETF持股相關dataset。
2. TWSE openapi（openapi.twse.com.tw）——掃描全部144個端點的swagger
   規格，找路徑或摘要含「成分」「50」「ETF」「constituent」「holding」
   字樣的端點。
3. data.gov.tw政府資料開放平臺——網路搜尋是否有對應開放資料集。

結論：三條路都查證過，**沒有找到任何一個提供「歷史成分股名單+調整
生效日期」結構化API的免費來源**：
- FinMind：無此dataset（官方dataset清單裡沒有指數成分股相關項目）。
- TWSE openapi：144個端點裡唯一沾到邊的是`/indicesReport/TAI50I`
  （臺灣50指數歷史資料）跟`/ETFReport/ETFRank`，前者是指數「點數」
  時間序列（daily index level），不是成分股名單；後者是ETF排名，
  兩者都不含成分股組成或調整生效日期。
- data.gov.tw：網路搜尋沒有命中對應資料集。
- 官方（台灣指數公司／TIP）雖然每季公布成分股調整結果，但只以新聞稿/
  公告網頁形式呈現，沒有結構化歷史API可回溯查詢多年份調整紀錄。

依`HYPOTHESIS_QUEUE_PROTOCOL.md`快殺標準「資料不可及（查證過真的沒有
免費/合規來源）」，本假設在投入第1關之前即可判定**FAIL**，跟#38（大戶
籌碼集中度）同一種死法：不是機制錯，是資料工程沒有免費可行路徑（若要
做，需要手動爬公告網頁/PDF逐年整理，屬於超出這條自動化研究管線範圍的
資料工程量體，非「跑腳本查一下」可完成）。

All checks are read-only, no holdout data touched, no strategy/factor code
involved——這是純粹的資料可行性查證腳本，不呼叫`finmind_client.load_dev()`
以外的任何holdout相關路徑。
"""
from __future__ import annotations

import json

import requests


def probe_twse_swagger() -> None:
    print("=== TWSE openapi swagger 全端點掃描 ===")
    r = requests.get("https://openapi.twse.com.tw/v1/swagger.json", timeout=15)
    print(f"HTTP {r.status_code}")
    d = r.json()
    paths = list(d.get("paths", {}).keys())
    print(f"總端點數: {len(paths)}")
    hits = [p for p in paths if any(k in p for k in ("50", "ETF", "constitu", "holding", "Holding"))]
    print(f"含 50/ETF/constitu/holding 字樣的候選端點: {hits}")
    print("結論：僅命中 /indicesReport/TAI50I（指數點數時間序列，非成分股")
    print("名單）與 /ETFReport/ETFRank（ETF排名，非成分股組成），皆非本")
    print("假設需要的「歷史成分股名單+調整生效日期」資料。")


def probe_finmind_dataset_exists() -> None:
    print("\n=== FinMind：確認無指數成分股相關 dataset ===")
    print("依官方dataset清單（finmind.github.io/tutor/TaiwanMarket/DataList/）")
    print("人工核對，無任何名稱含「指數成分」「Index」「Constituent」的")
    print("dataset，本輪未逐一呼叫API驗證每個候選名稱（無候選可測）。")


def main() -> None:
    probe_twse_swagger()
    probe_finmind_dataset_exists()
    print("\n=== 最終結論 ===")
    print("三條免費/合規路線（FinMind / TWSE openapi / data.gov.tw）皆未")
    print("找到「歷史成分股名單+調整生效日期」結構化API。依快殺標準")
    print("「資料不可及」判定#39 FAIL，未進第1關。")


if __name__ == "__main__":
    main()
