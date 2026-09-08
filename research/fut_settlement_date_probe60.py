"""#60（台指選擇權/期貨結算到期日機械性效應）資料可行性查證：能不能拿到
2015~2024 逐月真實歷史結算日，而不是自己「猜」規則。

**結論（三來源查證，符合 CLAUDE.md「搜尋紀律」）**：
1. 官方一手文件：TAIFEX 台指選擇權契約規格 PDF
   （https://www.taifex.com.tw/file/taifex/CHINESE/10/
   ％E8％87％BA％E6％8C％87％E9％81％B8％E6％93％87％E6％AC％8A％E4％B8％80
   ％E9％80％B1％E5％88％B0％E6％9C％9F％E5％A5％91％E7％B4％84％E6％91
   ％BA％E9％A0％81％E6％96％87％E5％AE％A3.pdf，2026-09-08 WebFetch 查證）：
   最後交易日＝到期月份「第三個星期三」，遇特殊情況（國定假日）順延。
2. 官方開放資料 API：`openapi.taifex.com.tw/v1/FinalSettlementPrice`
   （2026-09-08 curl 實測）——**只回傳近期快照**（實測窗口約 2025-10~12，
   僅約 10 個 TXO 結算日），**不含 2015~2024 歷史**，不能直接當歷史資料源。
3. 本專案既有基礎設施：`continuous_contract.py`（round 60/63/90/91 已驗證
   的滾動偵測邏輯，資料源是 `finmind_client.load_dev("TaiwanFuturesDaily",
   "TX", ...)`，TAIFEX 官方資料經 FinMind 轉手）——**這是本次實際採用的
   資料源**，理由見下方。

**為什麼不用「規則直接算」，改用「既有滾動偵測反推」**：
`continuous_contract.py` 的 docstring 已經證實 TX 單月合約「到期隔天就從
`TaiwanFuturesDaily` 消失」，所以每次前月合約切換的 `prev_date`（切換前一天）
就是真實發生過的結算日——這是**觀測到的事實**，不是套用規則算出來的猜測。
本次實測發現，2000~2024 共 300 個月裡有 7 個月**不是**標準「第三個星期三」
（例如 2015-02-24 是星期二、2023-01-30 是星期一，皆為農曆年期間交易所公告
調整），如果自己寫「每月第三個星期三」規則去推，這 7 個月全部會算錯——
這正是 `CLAUDE.md`「已知地雷」章節警告過的「未查證推算風險」的具體案例。
改用既有模組反推，這個風險直接歸零，而且零新增 API 呼叫（複用既有快取）。

**涵蓋範圍**：`FULL_HISTORY_END="2024-12-31"` 剛好對齊本專案 `VAL_END`，
天生不會洩漏 holdout。TRAIN（2015-01~2020-12）72 個月、VAL（2021-01~
2024-12）48 個月，兩期皆 100% 涵蓋、零缺口（每個月剛好一次滾動事件）。

**已知限制（誠實揭露，事前寫明）**：
- 這裡只驗證了 TX（台指期貨）的結算日。TXO（台指選擇權）依官方規格文件
  與 TX 同一套「第三個星期三」到期規則、理論上同一天結算，但這個假設本身
  未經資料驗證（`TaiwanFuturesDaily` 不含選擇權），若之後策略層需要選擇權
  本身的價格/成交量，需另外查證 `TaiwanOptionDaily`（FinMind）是否有對應
  資料且結算日確實與 TX 一致，不可默認為真。
- 這批日期只涵蓋「標準月合約」（`contract_date` 6 碼 YYYYMM），不含週選擇權
  （W1~W4，2013 年後才有）到期日——`#60` 假設本身鎖定的是月合約效應，
  週選擇權到期是另一個未測過的維度，不在本輪範圍內。
- 7 個非標準第三個星期三的月份，本輪只核對「是星期幾」與「落在月中哪天」，
  沒有逐筆去查證交易所當時的公告文號（例如農曆年調整公告）——如果之後
  策略層需要對這幾個特殊月份做敏感度分析，應視為「已知例外」而非「資料
  錯誤」，不要事後懷疑資料源本身有問題。

執行方式：`python fut_settlement_date_probe60.py`（read-only，只印結果+寫出
`data/fut_settlement_dates_derived_tx.csv`，不碰 holdout 之外的任何東西）。
"""
from __future__ import annotations

import pandas as pd

from continuous_contract import load_session, front_month_series, rollover_events

OUTPUT_CSV = "data/fut_settlement_dates_derived_tx.csv"


def derive_settlement_dates(contract: str = "TX") -> pd.DataFrame:
    """每一次前月合約滾動事件的 `prev_date`（切換前一天）＝該月真實結算日。
    複用 continuous_contract.py 既有已驗證邏輯，不重寫滾動偵測。"""
    df = load_session(contract, "position", "2000-01-01", "2024-12-31")
    front = front_month_series(df)
    events, skipped = rollover_events(df, front)
    if skipped:
        raise RuntimeError(f"未預期出現 skipped rollover events：{skipped}（歷史上應為 0，見 continuous_contract.py 既有驗證）")

    settle = (
        events[["prev_date", "old_contract"]]
        .rename(columns={"prev_date": "settlement_date", "old_contract": "contract_month"})
        .drop_duplicates(subset=["contract_month"])
        .sort_values("settlement_date")
        .reset_index(drop=True)
    )
    settle["settlement_date"] = pd.to_datetime(settle["settlement_date"])
    settle["weekday"] = settle["settlement_date"].dt.day_name()
    settle["day_of_month"] = settle["settlement_date"].dt.day
    settle["is_standard_third_wed"] = (settle["weekday"] == "Wednesday") & settle["day_of_month"].between(15, 21)
    return settle


def main() -> None:
    settle = derive_settlement_dates("TX")
    print(f"共反推出 {len(settle)} 個月的真實歷史結算日（2000-01~2024-12）")

    non_standard = settle[~settle["is_standard_third_wed"]]
    print(f"非標準「第三個星期三」的月份共 {len(non_standard)} 個：")
    print(non_standard.to_string(index=False))

    train = settle[(settle["settlement_date"] >= "2015-01-01") & (settle["settlement_date"] <= "2020-12-31")]
    val = settle[(settle["settlement_date"] >= "2021-01-01") & (settle["settlement_date"] <= "2024-12-31")]
    print(f"\nTRAIN 期（2015-01~2020-12）：{len(train)} 個月（預期 72），"
          f"非標準例外 {len(train[~train['is_standard_third_wed']])} 個")
    print(f"VAL 期（2021-01~2024-12）：{len(val)} 個月（預期 48），"
          f"非標準例外 {len(val[~val['is_standard_third_wed']])} 個")

    settle.to_csv(OUTPUT_CSV, index=False)
    print(f"\n已寫出 {OUTPUT_CSV}（{len(settle)} 列，可重複執行）")


if __name__ == "__main__":
    main()
