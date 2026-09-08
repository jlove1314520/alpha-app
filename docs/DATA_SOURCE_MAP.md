# DATA_SOURCE_MAP.md — 資料源可行性地圖

> 2026-09-08 建立（總司令裁示：查證結論要有固定登記處，**避免日後有人再提一次同一條路**）。
> 這份檔案記「哪些路走得通、哪些走不通、為什麼」。
> **看到某條路標 🔴，不要再重新評估一次，先看這裡的日期與理由。**

## 🔴 走不通：櫃買中心「產業價值鏈資訊平台」（ic.tpex.org.tw）

**查證日：2026-09-08。詳見 `docs/TPEX_INDUSTRY_CHAIN_GATE.md`。**

| 查證項 | 結果 |
|---|---|
| `ic.tpex.org.tw/robots.txt` | **302 Security Redirect、0 位元組，不存在** |
| `www.tpex.org.tw/robots.txt` | **HTTP 200 但內容是 404 頁**（「200 不等於成功」的老陷阱） |
| 使用條款 | **明文禁止爬蟲**（見下） |
| TPEx 官方 OpenAPI（225 端點） | **無價值鏈端點** |
| data.gov.tw | **無此資料集**，只有產業別（已有） |

條款原文：
> 「禁止透過包括但不限於自動化裝置、指令碼、自動程式、**蜘蛛程式、爬蟲程式**
> 或擷取程式等方式下載本網站之軟體或資料。」

**間隔拉到 3 秒也不改變它被禁止——速率不是重點，「用程式下載」本身就是被禁的行為。**

**唯一正途**：去信櫃買申請書面授權（條款寫「未經書面同意」不得重製，
反過來說書面同意是存在的途徑）。需總司令具名申請，Claude 不能代辦。

## 🔴 走不通：MOPS 公開查詢頁（mopsov.twse.com.tw）

**查證日：2026-09-08。** 這是總司令【裁示二】指定的替代路徑之一，**同樣不可走**。

```
GET https://mopsov.twse.com.tw/robots.txt   → HTTP 200

User-Agent: *
Disallow: /

User-Agent: bingbot
Allow: /mops/web
```

**除 bingbot 外，全站 `Disallow: /`。我們不是 bingbot，因此 MOPS 查詢頁不得程式取用。**

（`mops.twse.com.tw/robots.txt` 回 404、`mopsfin.twse.com.tw/robots.txt` 回 404 的
HTML 頁；但 `mopsov` 這台明確拒絕，而 `t05st03` 等查詢頁正是在 `mopsov` 上。）

## 🟢 走得通：TWSE 主站（www.twse.com.tw）

```
GET https://www.twse.com.tw/robots.txt   → HTTP 200

User-agent: Googlebot / Googlebot-News / OAI-SearchBot / GPTBot
Allow: /

User-agent: *
Disallow: /epaper/
Disallow: /FTSE/
Allow: /
```

**除 `/epaper/` 與 `/FTSE/` 外全部允許**，且明列允許 GPTBot 等 AI 檢索器。
我們既有的 `www.twse.com.tw/rwd/zh/fund/T86`（三大法人）**在允許範圍內，合規**。

註：TWSE 主站是 SPA，著作權/使用條款頁面在無 JS 時只回 747B 空殼，
無法以純 HTTP 取得條款全文——**已知限制，誠實記錄**。
robots.txt 是目前能取得的最明確意思表示。

## 🟢 走得通：TWSE／TPEx OpenAPI

`https://openapi.twse.com.tw/v1/`（143 端點）、
`https://www.tpex.org.tw/openapi/`（225 端點）。官方發布，設計上就是給程式讀的。

**但要知道它們沒有什麼**（2026-09-08 全表掃描確認）：
- ❌ 產業價值鏈上/中/下游分段
- ❌ **主要商品或服務項目及其營業比重**（368 個端點全掃，沒有）
  - `t187ap03_L`（上市公司基本資料，1,094 筆）只有**產業別**，無營業比重
  - `t187ap01` 是「各營業別**人員數**」（券商員額），**名稱容易誤中關鍵字，不是營收結構**

## 🔴 走不通：Stooq（已下市美股價格）

**查證日：2026-09-08。詳見 `docs/US_PRICE_SOURCES.md`。**
2026-03 起改 API key 制，key 需**人工過 CAPTCHA** 取得。資料本身免費無訂閱費。
**程式解 CAPTCHA＝禁止；人親自到官網領 key＝合規**，待總司令決定是否領。

## 🔴 更正：Stooq 的領 key 步驟我寫錯過（2026-09-08）

先前寫的逐步指南與實際頁面不符（總司令實測回報「根本就沒有你說的那些」）。
那不是親眼看到的畫面，是從第三方說明推得的，卻寫成了步驟一二三的形式——
**那個形式本身就在暗示已驗證，是誤導**。詳見 `docs/US_PRICE_SOURCES.md` 末段。
**Stooq 維持 🔴，除非總司令另有指示，不再嘗試。**

## 🟡 部分可用：Alpha Vantage（已實測，2026-09-08 key 已領）

**交叉驗證 ✅**：AAPL 與 yfinance 共同 100 日，收盤**差異率 0.0000%**。
**下市名冊 ✅**：`LISTING_STATUS` 免費可用，含 `delistingDate`。
**下市股價格 🟡**：TWTR（末日 2022-10-28、53.70）與 ATVI（2023-10-13、94.42）**正確**；
FRC 未收錄；**SIVB 是陷阱**——回傳的是破產後 OTC 空殼（0.006 美元、區間 2026 年），
不含 2023-03 崩潰期，**直接用會注入假的 −99.99% 報酬**。
**致命限制 ❌**：`outputsize=full` 與 `TIME_SERIES_DAILY_ADJUSTED` 皆為**付費**，
免費層只給**近 100 個交易日**且**未除權息調整**。
**100 天不足以回測**，故**未補起存活者偏誤缺口**，付費層標「待採購」。
客戶端與額度紀律：`research/av_price_client.py`（每日 22 次硬上限，用完誠實拒絕）。

## ~~🟡 未評估完：Alpha Vantage（已下市美股價格）~~

`LISTING_STATUS` 免費可用（demo key 實測回 426 筆真 CSV 含 `delistingDate`）；
價格序列需免費 key（填 email、**無 CAPTCHA**）。**待總司令決定是否領 key。**

## 🔴 不採用：鉅亨網 RSS

**查證日：2026-09-08（建置一.1）。** 兩個公開 RSS 路徑皆 404，
唯一可通的是 `api.cnyes.com` 的**站台後端 API**，違反取得方式鐵律「不撈 App／站台後端」。
日後若恢復公開 RSS 再加回。

## 🔴 本階段不接：LongPort OpenAPI（長橋）

**查證日：2026-09-07（Cowork）。總司令 2026-09-08 裁示本階段不開戶、不接入。**
- 行情涵蓋港股／美股／A 股，**不涵蓋台股**——對我方最缺的台股軌零幫助。
- 「免費」需分層：接口不另收開通費，但行情訂閱費在 App「行情商城」另計。
- 須完成開戶＋開發者認證才取得 token。速率：行情每秒 10 次、並發 5。
- 財報／估值／分析師評級屬**券商加工資料、無申報日可做 PIT 對齊**，
  **回測一律以 SEC EDGAR XBRL companyfacts 為準，不得改用券商衍生資料。**
- 僅在「App 要對外提供美股即時報價且本機 IBKR 無法修復」時才重新評估。

## 🟢 既有可用：本 session 的 IBKR MCP 工具

`get_price_snapshot`／`get_price_history`／`search_contracts`，
可作為美股報價與歷史的**交叉驗證來源，不需額外開戶**。
**限制**：對已下市美股 **0/4 覆蓋**（TWTR／SIVB／FRC／ATVI），
AAPL 對照組正常，故為下市股特有限制而非工具問題。
