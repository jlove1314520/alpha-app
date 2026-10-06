# 先.二十九-二 PIT 快照回放流程檢查表（Bb-90 自動再平衡）

只檢查流程；不含任何淨值、報酬或績效數字。假設每次用 100 萬新資金、零既有持股，僅用於走通流程。

| 月底 | 三檔資料可得(≤該日) | 資料新鮮度≤4日 | 無未來資料 | 目標權重加總=100% | 產生下單 | 硬限制閘門全過 | 結論 |
|---|---|---|---|---|---|---|---|
| 2026-05-29 | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 2026-06-30 | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 2026-07-31 | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 2026-08-31 | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 2026-09-30 | PASS | PASS | PASS | PASS | PASS | PASS | PASS |

整體：PASS

限制：資料來源為 data/price_history.json（僅約 90 列滾動窗，00646／00697B 在 2025-01 至 2026-05 之間有缺口）加 FinMind TaiwanStockPrice 補缺（補資料標的：['00646', '0050', '00697B']）；as-of 收盤；未回放券商對帳與實際成交（無歷史券商狀態可回放）。
