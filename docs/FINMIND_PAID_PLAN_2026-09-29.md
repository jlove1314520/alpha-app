# FinMind 付費贊助方案與額度查證（驗.九四，2026-09-29）

只查不買：未註冊、未輸入任何憑證、未付款。查證者為唯讀研究 agent，數字由 CC 依來源核對後整理。
**價格為新台幣、單次付款（不自動扣款）；請總司令親自開官網頁面確認現價，本表取自官網前端程式檔，非渲染後畫面。**

| 方案 | 價格 | 每小時請求上限 | 資料集數 | 授權 |
|---|---|---|---|---|
| Free（未登入、無 token） | $0 | 300 | 45 | 一般 |
| Free（註冊驗證信箱＋帶 token） | $0 | 600 | 45 | 一般 |
| Backer | $699/月；$5,499/年 | 1,600 | 81 | 非商業 |
| Sponsor（官網標「建議方案」） | $999/月；$8,888/年 | 6,000 | 97 | 非商業；不得把即時資料直接呈現於對外 web/App |
| Sponsor Pro | $3,330/月；$29,620/年 | 20,000 | 未查到總數 | 商業授權 |

- **每日／每月上限：三個來源都沒有寫**，官方只以「每小時」計。超限回 `HTTP 402 {"msg":"Requests reach the upper limit"}`。
- 用量可查：`GET https://api.web.finmindtrade.com/v2/user_info`（Bearer token，回 `user_count`／`api_request_limit`）。
- 所有付費方案可補差額升級（最低補 $100）。

## 與本專案的關係

- 本專案 `data/rate_limit_state.json` 的封鎖紀錄 `token_tail` 為空 → 當時是**無 token 的 300 次/小時層**。
- 免費註冊並帶 token 即可 300→600 次/小時（不花錢、需總司令本人註冊，CC 不代辦）。
- 驗.九二需補約 680 次請求：無 token ≈ 2.3 小時以上（本輪以 14 秒間隔節流，約 2.6 小時）；有 token（600/hr）約 1.2 小時；Backer 以上可 1 小時內完成。
- Backer 起有「單次下載特定日期全市場股價／三大法人／融資券」，可把「每檔一次」改成「每天一次」，請求量可能大幅下降（查證者未驗證實際扣次規則）。
- **授權提醒**：Backer/Sponsor 為非商業授權；Sponsor 明禁把即時資料直接呈現在對外 web/App，Alpha PWA 為公開 Pages，若付費需留意。
- 付費屬金流決策，本文件不作建議，由總司令決定。

## 三來源查證紀錄（七節）

1. 官網贊助方案頁 <https://finmindtrade.com/analysis/#/Sponsor/sponsor>（JS 動態載入，WebFetch 抓不到；改讀公開前端程式檔 `https://finmindtrade.com/static/js/chunk-4f103538.4b69191e.js`，價格、每小時上限、資料集數寫死在裡面）。
2. 官方 API 文件 <https://finmind.github.io/llms-full.txt>、`llms.txt`：註冊帶 token 600/hr、未帶 300/hr、超限 402；文件未列付費方案數字。
3. 官方 GitHub <https://github.com/FinMind/FinMind> README（300/600，無付費價格）＋社群文章（免費版每小時 600 次，掃到 400 多檔就爆），與官方一致。

## 與 2026-08-23 舊調查（commit `4bdda9314`，`research/REPORT.md`）對照

- 價格與每小時上限**完全相同**。
- 差異：Sponsor 資料集數舊調查 96 種、今天官網 97 種；Free 舊寫「300-600」，今天確認 300＝無 token、600＝註冊帶 token。
- 一則舊部落格寫註冊後「1500/hr」，與官方不符，判過時、不採信。

## 未確定

- 付費方案的實際扣次規則（例如整日下載算幾次）未查到。
- 官網若近日改價，以總司令親自開頁為準。
