# Alpha App — 進度紀錄

給協作用（包含另一個 Claude「Cowork」）看的進度紀錄。最新的寫在最上面，條列簡潔，讓沒看過對話的人也能接手。

---

## 2026-08-22 01:45 — 美股支援：自選股與個股頁可混台股＋美股

**改了什麼：**
清單第 2 項。驗證過 FinMind `USStockPrice`（欄位大寫：`Close`/`Open`/`High`/`Low`/`Volume`，沒有 `spread` 欄位，跟台股資料集欄位命名風格不同）與 `USStockInfo`（19,339 檔，欄位 `Country`/`IPOYear`/`MarketCap`/`Subsector`/`stock_name`，同一代號有重複列要取最新日期那筆）都可免費使用後，接進 App：
- 新增 `isUS(code)` 判斷式（代號開頭是字母＝美股，數字＝台股），不用改自選股 localStorage 既有格式，向後相容舊資料。
- `loadStockInfo()` 同時抓 TaiwanStockInfo + USStockInfo，本地快取分開存（`alpha_info` / `alpha_info_us`）。
- 搜尋視窗合併台股＋美股結果，用「· 美股／· 台股」標示。搜尋 AAPL 出來的結果第一批常常是槓桿/反向 ETF（如 GraniteShares 2x Long AAPL），不是 Apple 本人——這是 FinMind 資料庫的自然結果、不是 bug，使用者要自己認代號。
- 自選股列表、個股頁「總覽」分頁美股都能顯示即時價格與漲跌%（美股用 `$` 字首）。
- 個股頁「營收／財報／籌碼」三分頁對美股顯示「美股尚未支援…（僅適用台股）」，不是硬擠假資料或直接報錯。

**為什麼：**
使用者要求自選股與個股頁能處理美股，一樣要求先驗證資料集結構再動手。

**影響到哪些檔案：**
只改 `alpha-app/index.html`。新增 `isUS()`／`nameOf()` 共用函式；`hydrateHome()`、`loadStockInfo()`、`doSearch()`、`pickStock()`、`confirmDelete()`、`openStock()` 都加了美股分支，台股原本邏輯完全沒動（用 `if(us){...return}` 提前返回的方式隔離，降低改壞台股功能的風險）。

**測試方式：**
本機伺服器 + Chrome：搜尋 AAPL → 加入 Apple Inc. → 確認自選股列表混合顯示台股/美股（顏色、$ 字首、市場標籤都對）→ 開 AAPL 個股頁確認總覽顯示真實股價、營收/籌碼分頁正確顯示「暫無資料」提示 → 回頭開台積電（2330）個股頁確認 PER/殖利率/YoY/PBR 都還是正常真實資料（沒有因為這次改動壞掉）。Console 無錯誤。

**下一步：**
清單第 3 項——個股「財報」分頁接 `TaiwanStockFinancialStatements`（真實 EPS/毛利率），一樣要先 fetch 驗證欄位與是否免費。

**卡住的問題：**
無。

---

## 2026-08-22 01:15 — 市場頁接真實資料（大盤指數／類股／三大法人／期貨籌碼）

**改了什麼：**
把「市場」分頁（`scr-market`）4 張卡片的示範資料全部換成 FinMind 真實資料：
1. 新增「大盤指數」卡：加權指數（`TaiwanStockPrice` data_id=`TAIEX`）、櫃買指數（data_id=`TPEx`，注意大小寫）。
2. 「類股表現」熱力圖：改用 8 個 FinMind 官方產業類股指數（`Semiconductor`／`Electronic`／`CommunicationsInternet`／`Optoelectronic`／`FinancialInsurance`／`ElectricMachinery`／`ShippingTransportation`／`Tourism`，都是 `TaiwanStockPrice` 的 data_id），顏色依漲跌幅（±3% 封頂）動態插值紅／綠。原本「AI 伺服器／光通訊」這種非官方分類名稱拿掉了，因為 FinMind 沒有對應資料集，換成 FinMind 官方 27 類產業指數中的真實類別，避免掛羊頭賣狗肉。
3. 「三大法人買賣超（近5日）」：改用 `TaiwanStockTotalInstitutionalInvestors`（不用帶 data_id，市場總表），取每日 `name=='total'` 那筆的 `buy-sell` 當作全市場三大法人合計淨額。
4. 「期貨籌碼」卡整張重做：原本「大額交易人前十」「P/C Ratio」「現股當沖佔比」這三個數字查證後發現要付費（FinMind 回傳 `Your level is free. Please update your user level`），免費方案生不出來，用了會變成新的假資料，所以拿掉。改成 `TaiwanFuturesInstitutionalInvestors`（要帶 `data_id=TX` 才能免費用，不帶會被當付費資料集擋掉——這是這次踩到的新坑，見下方）算出的外資／投信／自營商／三大法人合計「台指期未沖銷淨部位（口）」，全部可免費取得。

**為什麼：**
使用者要求把市場頁能換真的就換真的，並且規定「用任何新資料集前要先實際 fetch 驗證欄位結構與是否免 token」。這次照規則全部用 curl 先驗證過（見下方新踩的坑），沒有用猜的。

**影響到哪些檔案：**
只改了 `alpha-app/index.html`（HTML 結構 + `<script>` 內新增 `hydrateMarket()`、`loadMarketIndex()`、`loadHeatmap()`、`loadInstTotal()`、`loadFutInst()` 等函式；`go()` 加一行在切到市場頁時呼叫 `hydrateMarket()`）。沒有動到 `alpha-data` 任何東西。

**新踩到的坑（給以後接手的人）：**
- FinMind 有些資料集（例如 `TaiwanFuturesInstitutionalInvestors`、`TaiwanFuturesDaily`、`TaiwanOptionDaily`）**不帶 `data_id` 查詢會被誤判成付費限制**（回傳 `status:400, "Your level is free..."`），但**帶對 `data_id`（如 `TX`）就能免費正常回傳**。所以看到這個錯誤訊息不能直接認定「這個資料集要收費」，要先試著帶對的 data_id 再下結論。
- 確認**真的要收費、免費方案拿不到**的資料集（試過帶 data_id 依然 400）：`TaiwanFuturesOpenInterestLargeTraders`（大額交易人）、`TaiwanStockDayTrading`（當沖）、`TaiwanStockMarginPurchaseShortSale`。這幾個之後不用再試了。
- 櫃買指數的 data_id 是 `TPEx`（大寫 T P E 小寫 x），大小寫打錯會查不到資料但不會報錯（回傳空陣列），要注意。
- FinMind 官方完整資料集清單，可以故意送一個不存在的 dataset 名稱，它的 400 錯誤訊息會列出全部合法值，比翻文件快：`curl "https://api.finmindtrade.com/api/v4/data?dataset=INVALID"`。

**測試方式：**
用 `python -m http.server` 在本機起一個靜態伺服器，Chrome 開 `localhost` 測試（`file://` 直接開會被瀏覽器工具擋，且部分瀏覽器對 file:// 的 fetch 有限制，起本機伺服器比較保險）。四張卡都截圖確認數字有出來、顏色邏輯正確（三大法人合計 = 外資+投信+自營商 驗算過），也重新走了一次「今日」頁自選股、個股頁三分頁，確認沒有壞掉（回歸測試）。Console 沒有錯誤。

**下一步：**
繼續清單第 2 項——美股支援（FinMind `USStockPrice`／`USStockInfo`，一樣要先 fetch 驗證）。

**卡住的問題：**
無。

---

## 2026-08-22 00:41 — 修好 git push 卡住的問題（改用 PAT）

**改了什麼：**
本機執行 `git push` 時會用 Git Credential Manager 的瀏覽器 OAuth 登入，但該登入視窗會開在 Bash 工具背後的隱藏主控台，使用者完全看不到、指令永遠卡住逾時。改用 GitHub Fine-grained Personal Access Token（範圍限定 `jlove1314520/alpha-app`，Contents 權限 Read/write），透過 `git credential approve` 直接存進 Windows 的 Git Credential Manager，跳過互動登入流程。

**為什麼：**
之前的 PROGRESS.md 初版 commit 因為這個問題卡住 push 超過 2 分鐘，逾時失敗。改用 PAT 後 push 立即成功、無需任何互動。

**影響到哪些檔案：**
無程式碼變動，只有這台機器本機的 Git 憑證設定（Windows Credential Manager，host=github.com）。之後這台機器上任何 github.com 的 repo push 都會直接用這組憑證，不會再跳窗。

**下一步：**
無（此問題已解決）。若之後 PAT 過期或被撤銷、push 又開始卡住，直接跟使用者要新的 PAT，重複 `git credential approve` 設定，不要再嘗試瀏覽器登入流程。

**卡住的問題：**
無。

---

## 2026-08-22 00:33 — 交接、建立開發環境、寫專案說明文件

**改了什麼：**
- 從 GitHub clone `jlove1314520/alpha-app` 到本機 `C:\alpha\alpha-app\`，之後開發改在本機直接進行，不再手動下載上傳。
- 檢查 repo 內容：index.html、manifest.webmanifest、sw.js、icon192.png、icon512.png，確認沒有多餘的重複舊檔（如 `index (1).html`）需要清除。
- 確認本機 Git Credential Manager 已設定好，push 時會走瀏覽器登入，不需額外設定。
- 在使用者桌面建立捷徑「Alpha」（`C:\Users\user\Desktop\Alpha.lnk`），雙擊會開 PowerShell、cd 進 `C:\alpha`、自動啟動 `claude`。對應腳本 `C:\alpha\start-alpha.bat`。
- 新增 `C:\alpha\CLAUDE.md`，整理專案結構、功能現況、關鍵決策、已知地雷（給任何接手這個 repo 的人快速上手用）。

**為什麼：**
使用者原本是手動下載 index.html 改完再上傳到 GitHub，效率差也容易漏東西。改成在本機用 Claude Code 直接開發、直接 git commit+push，取代舊流程。

**影響到哪些檔案：**
- 新增：`C:\alpha\CLAUDE.md`（不在此 repo 內，在上層目錄）
- 新增：`C:\alpha\start-alpha.bat`（不在此 repo 內）
- 新增：本檔案 `PROGRESS.md`
- 沒有修改 `alpha-app` 內任何既有檔案（index.html 等維持原樣）
- 沒有動到 `C:\alpha\alpha-data\alpha.db` 或任何 Python 資料管線檔案

**下一步：**
等使用者指示要接哪個功能。候選方向：
1. 市場頁類股/大盤真實資料
2. 美股報價（FinMind `USStockPrice`）
3. AI 盤前日報接真實新聞
4. Phase 2 券商下單研究（Shioaji / IBKR）

**卡住的問題：**
無。

---

## 專案背景（不常變動，供快速定位）

- 手機 PWA：本 repo，單一自包含 `index.html`，client-side 直接打 FinMind 免 token API。線上網址 https://jlove1314520.github.io/alpha-app/ ，push 後 GitHub Pages 約 1–2 分鐘自動部署。
- Python 資料管線（不在本 repo，在 `C:\alpha\alpha-data\`，未來 Phase 2 自動下單用）：`alpha.db` 絕不可刪除或覆蓋；`fetch.py`/`parsers.py`/`config.py` 的資料源邏輯是踩過坑調好的，不要順手重構。
- 完整背景/決策紀錄/已知地雷見 `C:\alpha\CLAUDE.md`（不在本 repo，在上層目錄，因為要涵蓋 alpha-data 部分）。
