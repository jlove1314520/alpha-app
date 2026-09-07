# 美股價格資料源查證紀錄（資料源一.3）

> 2026-09-08。依 CLAUDE.md「搜尋紀律：三來源查證」與「取得方式鐵律」建立。
> 這份檔案記錄的是**查證過程**，不是結論摘要——之後任何人想推翻這裡的判斷，
> 要先看得到我當時查了什麼、看到什麼。

## 結論先行

| 來源 | 在市股 | **已下市股** | 取得方式 | 現況 |
|---|---|---|---|---|
| yfinance（現行主來源） | ✅ | **❌ 完全沒有** | 免費、免 key | 使用中 |
| Stooq | ✅ | ✅（宣稱含） | **免費但需 API key，key 要人工過 CAPTCHA 領** | **待總司令領 key** |

**核心問題：現行主來源 yfinance 對已下市股 0 覆蓋。**
資料源一.1 建好的 PIT 宇宙有 10,863 檔，其中已下市 775 檔（7.1%）**沒有任何價格來源**。
存活者偏誤只補了一半——補到了「知道誰倒了」，還沒補到「倒之前價格怎麼走」。

## 一、yfinance 對已下市股的實測（2026-09-08）

```
AAPL   在市對照           →  2932 筆  2015-01-02 ~ 2026-08-31 ✓
TWTR   2022 私有化下市     → 無資料 ✗
SIVB   2023 破產下市       → 無資料 ✗
FRC    2023 被 JPM 接收下市 → 無資料 ✗
ATVI   2023 被微軟併購下市  → 無資料 ✗
```

Yahoo 回的是 `possibly delisted; no timezone found`——這是它對已下市代號的標準回應，
不是暫時性錯誤。**4/4 全滅，對照組正常**，所以不是網路或環境問題。

**推論**：yfinance 的母體跟 FinMind `USStockInfo` 犯的是同一個錯——它是「還在交易的
標的」的資料庫。我們在資料源一.1 花力氣換掉 FinMind 宇宙，換來的宇宙卻餵不進現行價格源。
**宇宙與價格必須同時是 survivorship-free 才有意義，只修一邊等於沒修。**

## 二、Stooq 三來源查證

依紀律要求涵蓋 4 類來源中的至少 3 類。

### （1）官方網站直接實測
| 端點 | 結果 |
|---|---|
| `https://stooq.com/q/d/l/?s=aapl.us&i=d` | HTTP **200 但回 HTML**，內容是 JS 工作量證明驗證頁 |
| `https://stooq.com/q/l/?s=aapl.us&f=...&e=csv` | HTTP **404** |
| `https://stooq.pl/q/d/l/?s=aapl.us&i=d`（波蘭原始域名） | 同樣的 JS 驗證頁 |

驗證頁內容：要求瀏覽器用 `crypto.subtle.digest` 對一個 challenge 字串反覆 SHA-256，
湊出 4 個前導零的雜湊，再 POST 到 `/__verify`。

**注意這是「200 + HTML」**，跟 CLAUDE.md 已知地雷裡 `openapi.twse.com.tw` 的陷阱一模一樣。
只看狀態碼會誤判成成功。

### （2）GitHub／社群
pandas-datareader issue #1012「Stooq now requires API key - Documentation update needed」
（2026-04 開立）：`pandas_datareader.DataReader` 對 Stooq 失敗並拋 `ParserError`，
因為 Stooq 回的是「請申請 API key」的 HTML 而不是 CSV。
→ https://github.com/pydata/pandas-datareader/issues/1012

這條證實了**不是我們被個別封鎖，是 Stooq 在 2026 年 3 月改了存取模式**。

### （3）其他供應商／第三方說明
多方資料一致指出：Stooq 資料**本身免費、沒有訂閱費**，涵蓋 21,000＋ 全球標的、
數十年歷史；2026 年起存取需 API key，**key 經由網站上的 CAPTCHA 取得**，
並有每日請求額度上限（超過回 `Exceeded the daily hits limit`）。

## 三、取得方式鐵律怎麼適用（重要，別誤讀）

我**有能力**用幾行 Python 解掉那個 SHA-256 工作量證明。**沒有做，也不准做。**
鐵律列舉的禁止形式包含「解驗證碼」「換 IP 或加代理規避速率限制」，
且寫明「不論是否對外使用——自用、研究、只跑一次通通不算例外」。

**但這不代表 Stooq 出局。** 要分清楚兩件事：

- ❌ **程式自動解掉 CAPTCHA／PoW 拿資料** = 繞過，禁止。
- ✅ **人到官網用正常流程過一次 CAPTCHA、領一把官方發的免費 key** = 走官方途徑，
  正是鐵律要求的「只走官方 API 與文件」。

所以正確做法不是硬取，也不是放棄，而是**請總司令親自領一次 key**。
這件事我不能代勞：代勞就等於自動解 CAPTCHA。

## 四、待總司令決定

要接 Stooq 當第二來源與下市股價格源，需要總司令做一次（約 2 分鐘）：

1. 開 https://stooq.com/ ，找 API／key 申請入口
2. 過一次 CAPTCHA，領到 key
3. 把 key 貼給我，我存到 **repo 外**（比照 `fred_key.txt` 的既有慣例，
   本 repo 是 Public，金鑰絕不進 commit）

拿到 key 之後我才能做裁示指定的那件事：**兩來源對同一 ticker 同一日收盤的差異率**。
**現在報不出這個數字，因為只有一個來源拿得到資料。**

若總司令不想領 key，備選方向（都還沒查證，不要當結論）：
Tiingo、Polygon.io、Nasdaq Data Link、EODHD。這幾家對下市股的覆蓋與價格要另外查。

## 五、對其他項目的影響

- **資料源一.4（4 個美股因子在新宇宙重跑）**：**擋住了**。
  新宇宙有 775 檔下市股，價格拿不到，重跑等於還是只跑在市股，
  跟舊結果的差別只剩宇宙定義，證明不了偏誤已修正。
- **外部一改.1**：原本就在等一.4，繼續等。
- 在價格源補齊之前，**所有美股結論一律維持「宇宙待驗證」標記**，不得升級。

---

# 續查：已下市美股歷史價格（2026-09-08 資料源一.3 續）

總司令裁示依序查證三條免費且合規的來源，每條都實測 TWTR／SIVB／FRC／ATVI 四檔。

## 總表

| 來源 | 下市股覆蓋 | 需要 key | 結論 |
|---|---|---|---|
| yfinance（現行主來源） | **0/4** | 否 | 不可行 |
| **(a)** IBKR MCP 工具 | **0/4** | 否（既有資源） | **不可行** |
| **(b)** SEC EDGAR XBRL | 端點價，**不成序列** | 否 | **不足以支撐回測** |
| **(c)** Alpha Vantage 免費層 | **未測完** | **是（免費、無 CAPTCHA）** | **待總司令決定是否領 key** |
| Stooq | 宣稱有 | 是（**需人工過 CAPTCHA**） | 待總司令決定 |

## (a) IBKR MCP — 0/4，不可行

| 標的 | `search_contracts` | `get_price_history` |
|---|---|---|
| **AAPL（對照組）** | ✓ | ✓ **22 根日 K，正常** |
| TWTR | ✓ 找到 2 個 contract（137780444、145142887，exchange 皆 `VALUE`） | ✗ 兩個都回 `Details currently unavailable` |
| SIVB | ✗ 普通股查無，只有債券與特別股 `SIVBO` | — |
| FRC | ✗ 查無 | — |
| ATVI | ✗ 查無 | — |

**對照組是關鍵**：AAPL 同一支工具同一時間正常回傳，所以 TWTR 的失敗**不是工具當下不通，
是下市股特有的**。IBKR 保留了部分合約 metadata（TWTR 還查得到名字），
但**歷史 K 線一律不給**。

## (b) SEC EDGAR XBRL — 只有端點價，不成序列

查 `dei:EntityPublicFloat`（10-K 封面頁的公眾流通市值）與
`dei:EntityCommonStockSharesOutstanding`：

| 公司 | EntityPublicFloat | SharesOutstanding |
|---|---|---|
| SVB Financial（SIVB，CIK 719739） | **13 筆**，最後 2022-06-30 = 23,336,532,366 USD | 51 筆，最後 2023-01-31 = 59,200,925 |
| Twitter（TWTR，CIK 1418091） | **8 筆**，最後 2021-06-30 = 53,550,000,000 USD | 34 筆，最後 2022-07-22 = 765,246,152 |
| First Republic（FRC，CIK 1132979） | **完全沒有 companyfacts** | — |

**結論：一年最多一個端點價，不構成序列**，正如總司令預判。

**額外的誠實揭露（重要）**：`EntityPublicFloat` 是**非關係人持股**的市值，
不是總市值。拿它除以「總」流通股數，得到的是**價格下界，不是價格**。
就算只當端點價用，這個偏差也必須標明。

Form 25 只給下市**日期**，不給價格。

## (c) Alpha Vantage — 未測完，需要一把免費 key

- `LISTING_STATUS` 端點**免費可用且回真 CSV**：demo key 查 `date=2014-07-10&state=delisted`
  回 **426 筆**，欄位含 `ipoDate`／`delistingDate`／`status`。
  → **下市「名冊」這一半 Alpha Vantage 給得起。**
- 但 demo key **只支援官方文件那一個示範日期**：改成 `date=2023-06-01` 回 `{}`（0 筆），
  所以查不到 2022/23 才下市的那四檔。
- `TIME_SERIES_DAILY` 對 TWTR 回：
  `"The **demo** API key is for demo purposes only. Please claim your free API key…"`

**所以「下市股價格序列」這一半沒測到，不是不可行，是缺 key。**

**我沒有自行去領**：領 key 要提交 email，等於**拿總司令的信箱去註冊第三方服務**。
這不在「純 bug 修復」或「已明確交辦」的範圍內，依提案先於執行，交總司令決定。

## 目前結論（誠實版）

**還不能說「已下市美股價格無合規免費來源」**——(c) 尚未測完。
能確定的是：**(a) 與 (b) 都補不了這個缺口**，而 (c) 與 Stooq 都卡在同一件事上：
**需要總司令花一兩分鐘親自領一把 key。**

兩條路的取得成本比較：

| | Alpha Vantage | Stooq |
|---|---|---|
| 費用 | 免費 | 免費（無訂閱費） |
| 取得方式 | **填 email，無 CAPTCHA**，官方稱「不到 20 秒」 | **需人工過一次 CAPTCHA** |
| 額度 | 免費層有每日次數限制 | 有每日額度上限 |
| 下市股價格 | **未證實** | 宣稱有，未證實 |

**建議先領 Alpha Vantage**（成本更低、無 CAPTCHA），測完再決定要不要動 Stooq。
