# 解凍提案前置條件清單

建立：2026-10-13（總司令【先.八十二】2 裁示①）。2026-10-15 先.一〇二-5 加第 5 項。

目前資金凍結（STOP 旗標＋strategy_frozen）。**只有總司令另行裁示才能解凍**；任何「請求解凍」的提案，必須逐項附上下列條件的證據。缺一項就不算完整的解凍提案。

| # | 前置條件 | 驗收方式 | 來源 |
|---|---|---|---|
| 1 | Shioaji 由 1.7.4 升到 1.7.7（**禁止 1.7.6**） | `pip show shioaji` 版本輸出 | 先.四十九、先.八十二-2 |
| 2 | 升級後唯讀 `--preflight` 全 PASS | preflight 輸出全文（帳號、金額遮蔽） | 先.八十一-2 |
| 3 | SIMULATION 模擬演練 A（盤中模擬成交）PASS | 演練紀錄 | 先.八十一-2 |
| 4 | SIMULATION 模擬演練 B PASS | 演練紀錄 | 先.八十一-2 |
| 5 | 重開機停擺防護已上線並驗證：第一批排程（AlphaMarketCatchup／AlphaMarketCatchupLate／AlphaData／AlphaQuotesFallback／AlphaWarrantSnapshot／AlphaDevQueue）已改「不論登入與否都執行」，且實測沒登入時會跑、推得上 GitHub | `Get-ScheduledTask` 的 LogonType＝Password＋非互動身分執行與 push 紀錄（`docs/PROPOSAL_REBOOT_OUTAGE_GUARD.md` 驗收節） | 先.一〇一、先.一〇二-5 |

## 說明

- 演練 A／B 需要暫切 SIMULATION 並撤 STOP 旗標，**只能在總司令開出演練窗口時做**；CC／Cowork 不得自行切模式或撤旗標。
- 任一項失敗：退回 1.7.4，解凍提案不成立。
- 凍結期間維持 Shioaji 1.7.4（2026-10-13 裁示①）。
