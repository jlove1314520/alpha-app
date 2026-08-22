# Alpha App — 進度紀錄

給協作用（包含另一個 Claude「Cowork」）看的進度紀錄。最新的寫在最上面，條列簡潔，讓沒看過對話的人也能接手。

---

## 2026-08-23 01:30 — AI 選股引擎「選股」分頁上線 + 準備開 30 分鐘挖礦馬拉松

**發生什麼事：** `research/` 底下的 AI 選股引擎（用真實資料算出「哪些股票比較值得看」）走完全部步驟，現在 App 上多了一個「選股」分頁可以看結果。

**這次做了什麼（白話版）：**
1. 上一輪找到 4 個「真的有用」的訊號（不是隨便猜的，是統計檢定過的），但其中兩個（EPS成長、EPS意外）其實在講同一件事，這次先把它們合併，避免同一個訊號被算兩次分數。
2. 把訊號組合成一個「綜合分」，同產業的股票互相比較（不會拿半導體股跟航運股比，不公平）。
3. **最重要的驗證**：假裝真的照這個分數買賣股票，然後跟「隨機亂挑股票」比賽（用同樣的換股頻率、同樣的手續費），看綜合分是不是真的比亂猜強。**結果：完勝，兩個測試期間都贏過全部 60 次隨機亂挑**——這代表這套選股邏輯不是巧合，是真的有訊號。（誠實補充：如果拿去跟「完全不換股，一開始買了就放著不動」比，反而是後者賺得多，因為常常換股要付很多手續費——這不代表選股沒用，是「常換股」這個做法本身成本高，是兩個不同的問題。）
4. App 新增「選股」分頁，可以看排行榜、點進去看每檔股票的訊號拆解。已經用瀏覽器實際點過，正常運作。

**誠實聲明（App 上也有寫）：** 這是研究/教育用途，不是投資建議；歷史測試結果不代表以後也會這樣；目前排行榜用的是 2024 年底的資料當範例，不是即時資料（每天自動更新是下一步，還在討論怎麼做才安全）。

**影響到哪些檔案：** `index.html`（新增選股分頁）、`scores.json`（新增，選股資料）、`research/` 底下多個新檔案（技術細節見 `research/STRATEGY_LOG.md`/`research/FACTORS.md`）。

**下一步：** 設定讓電腦每 30 分鐘自動跑一次「挖礦」（自動找新的可能有用的訊號/策略，台股/美股/期貨分開找），全程遵守不能碰「holdout」資料、不能自動真的下單這些鐵律。

**卡住的問題：** 每天自動更新「選股」排行榜這件事，牽涉到一個資料使用規則的問題，還在等使用者決定怎麼處理最安全。

---

## 2026-08-22 12:00 — 回應 Cowork 稽核回報：research/*.py 404 問題排查

**發生什麼事：** Cowork 回報 `research/` 底下只有 `.md` 讀得到，`holdout.py`／`costs.py` 等 `.py` 在 GitHub 上是 404，沒辦法稽核。

**排查結果：** 用四種獨立方式交叉核對（本機 `git log`/`git status`、`git fetch` 後比對 `origin/main`、對每個 `.py` 檔直接 curl `raw.githubusercontent.com` 確認 HTTP 200、GitHub API `contents`/`commits` 端點直接核對目錄內容跟 commit SHA）——**這次稽核當下，全部 `.py` 檔案確實都在 GitHub 上、讀得到**，跟本機 `git rev-parse HEAD` 逐字元一致。判斷 Cowork 回報的當下是抓到舊快照（可能查在某次 push 完成之前，或它那邊的 clone 沒 pull 到最新），不是這邊 push 流程真的漏了東西。

**已補強（即使這次沒查到真的問題，還是照使用者要求做了三件事，降低以後再發生類似誤會或真的漏推的機率）：**
1. `research/STRATEGY_LOG.md` 最上面加了 **FILE MANIFEST** 區塊：逐檔列出 repo 相對路徑＋一句用途＋型態，附上這次的驗證方式跟時間戳（含驗證用的 commit SHA），讓任何人以後都能照同一套方法重新核對，不用每次重新摸索。
2. `.gitignore` 追加防禦性規則（`*.parquet`／`*.db`／`fred_key.txt`／`.env`，目前 repo 裡都還沒有這些檔案，純粹預防），並加註解明確警告「不要加裸的 `*.py` 或 `research/` 規則」——避免以後有人為了「乾淨一點」誤改成把整個資料夾擋掉，重演這次的問題（這次不是這個原因，但這是最容易導致這種問題的錯誤，先防起來）。
3. 用 `git check-ignore` 對全部已追蹤的 `.py` 檔跑過一輪，確認新加的規則沒有誤擋任何一個。

**影響到哪些檔案：** `.gitignore`、`research/STRATEGY_LOG.md`（新增 FILE MANIFEST）、`research/REPORT.md`（append 一條完整排查記錄）、`research/MARATHON_STATE.md`（狀態快照加註稽核通過時間）。沒有動到任何 App 程式碼。

**下一步：** 等 Cowork 用同樣方式（GitHub API 或 raw content）重新確認一次。如果之後又回報類似問題，先照 `STRATEGY_LOG.md` 的 FILE MANIFEST 走一次驗證流程再下結論，不要預設是自己這邊漏推、也不要預設對方一定錯。

**卡住的問題：** 無。

---

## 2026-08-22 03:40 — 真正的設定頁、個股走勢圖接真資料、修一個台指期夜盤 bug

**改了什麼：**
使用者把優先序調回 App 前端（Phase 2 研究先放背景）。這輪指定的三項：

1. **設定頁**：原本點下去只跳 toast，現在是真的畫面（`scr-settings`）。券商帳戶（台股/美股備註，行內輸入框、失焦自動存，**沒有用 `prompt()`**——原本設計是跳瀏覽器原生對話框，但那會擋住自動化測試、在手機 PWA 上視覺也跟其他畫面不搭，改成跟風控參數一致的行內輸入框）；風控參數（每日虧損上限/單筆部位上限/最大持倉檔數，存 localStorage，按「儲存」才寫入並顯示時間戳）；通知偏好（3 個開關，點了立刻存，不用另外按儲存）；自選股管理入口（連到既有搜尋視窗）；資料來源狀態（即時顯示目前 `localStorage` 裡 FinMind 快取筆數）；關於/版本。全部設定重開頁面後都還在，測試過。
2. **市場頁真實資料**：這項在更早之前的回合已經做過了（加權指數/櫃買指數/三大法人買賣超都已接真資料），這次只是重新驗證一次還正常，沒有重做。
3. **個股頁「總覽」走勢圖**：原本是寫死的示範折線，現在用個股頁本來就會抓的近月收盤價（`_d(16)`→`_d(35)`，多抓一點天數）畫真實線圖，改動最小（沒有另外多打一次 FinMind，重用同一份資料）。台股來源標註誠實提醒「原始未還原股價」（呼應 `research/DATA.md` 的還原股價發現）；美股標「$」字首。

**意外抓到的 bug（測試時發現）：**
台指期近月那格（「今日」頁大盤速覽跟市場頁都有）偶爾會顯示「查無資料」，明明資料其實有。原因：TAIFEX 夜盤（`after_market` 場次）掛在**下一個**交易日的日期上，原本邏輯是抓「資料裡最新的日期」再篩日盤（`position`）場次，如果最新那個日期只有夜盤、日盤還沒開盤，篩出來就是空的。修法：改成先找「有日盤資料」的最新日期，不要直接抓最大日期。已修正並重新驗證過。

**影響到哪些檔案：**
只改 `alpha-app/index.html`。新增 CSS `.setting-row`/`.setting-input`；新增 `scr-settings` 區塊、`hydrateSettings()`/風控/通知/券商相關函式；新增共用的 `trendChart()` 繪圖函式（`spark()` 旁邊，共用邏輯）；`futNearRow()` 修掉上述 bug。

**測試方式：**
本機伺服器 + Chrome：設定頁全部欄位都手動改過一輪、重整頁面確認 localStorage 持久化正確；個股頁走勢圖台股（2330）跟美股（AAPL）都截圖確認是真實線圖不是示範資料；市場頁、今日頁大盤速覽重新整個走一輪確認台指期近月 bug 修好、其餘功能沒有回歸。Console 全程無錯誤。

**下一步：**
等使用者下一輪指示。Phase 2 研究（里程碑 2 剩餘部分）持續背景進行。

**卡住的問題：**
無。

---

## 2026-08-22 02:50 — 體驗優化：今日頁大盤速覽接真資料、加上快取與斷線容錯

**改了什麼：**
清單第 4 項。範圍刻意收斂在「有免費真實資料可換、且不用大改版面」的項目：
1. **「今日」頁大盤速覽卡**（原本是示範資料）換成真的：加權指數（沿用市場頁驗證過的 `TAIEX`）、台指期近月（`TaiwanFuturesDaily` data_id=`TX`，抓最新交易日、`trading_session==='position'`、排除價差合約、取合約月份最小的當「近月」，spread/spread_per FinMind 直接給不用自己算）、NASDAQ（新驗證：`USStockPrice` data_id=`^IXIC` 免費，這是真的 Nasdaq Composite 指數，不是 ETF 代APPROX）。三個資料源都先 curl 驗證過才接。
2. **FinMind 抓取加上 localStorage 快取**（3 分鐘 TTL）：原本的 `_cache` 只是記憶體內快取，重新整理頁面就沒了；現在同一份資料 3 分鐘內重整頁面也不會重打 FinMind，直接減少 API 用量。
3. **斷線容錯**：`fm()` 抓取失敗時（網路問題、FinMind 暫時掛掉）不再直接回傳空陣列（會被 UI 誤判成「查無資料」），改成退回上一次成功抓到的快取（即使過期也用），並在 console 印警告方便除錯。使用者實際看到的畫面會是「稍舊但正確」的數字，而不是被誤導成「這檔沒資料」。

**為什麼：**
使用者要求小幅體驗優化：載入中/錯誤狀態、FinMind 快取、修掉殘留假數字，且明確說不要大改版面。

**影響到哪些檔案：**
只改 `alpha-app/index.html`。`idxRow()` 加了第 4 個參數 `ds`（資料集名稱，預設 `TaiwanStockPrice`）讓它能重用在美股指數上；新增 `futNearRow()`、`loadHomeIndex()`；`fm()` 內部改用 `fmCacheRead/fmCacheWrite/fmCacheStale` 三個新函式做 localStorage 快取。市場頁跟個股頁呼叫 `fm()`/`idxRow()` 的地方完全沒動，因為新參數是可選的、有預設值，向後相容。

**還沒動的「假數字」（刻意跳過，原因見下）：**
- 「今日」頁 KPI（總資產/已實現損益）、「交易」頁機器人與委託紀錄、「日誌」頁損益紀錄——這些需要真實券商帳戶/API 金鑰才有意義，屬於 Phase 2（券商串接），照規則不可自己動手接。
- AI 盤前日報/AI 盤勢解讀/AI 個股簡報——這些是示範文字，接真實新聞是另一項工作（清單外），沒有在這次範圍內動它們，內容本身已經誠實標註是原型。
- 個股頁「走勢（日K區）」圖表——本來就已經誠實標註「原型示意．正式版接 Shioaji/IBKR 即時行情」，不需要改。

**測試方式：**
本機伺服器 + Chrome：「今日」頁確認大盤速覽三列都是真數字（加權指數/台指期近月/NASDAQ），用 JS console 確認 `localStorage` 裡出現 9 筆 `fmc_` 開頭的快取項目；市場頁重新開一次確認沒有因為 `idxRow()` 改簽章而壞掉（TAIEX/TPEx 兩列一樣正常）。Console 全程無錯誤。

**下一步：**
清單第 1–4 項已全部跑過一輪。等使用者回饋，或視情況回頭把某幾項做得更細（例如市場頁 AI 卡文字改成依真實漲跌動態生成，而不是純靜態文案）。

**卡住的問題：**
無。

---

## 2026-08-22 02:30 — 個股「財報」分頁接真實 EPS/毛利率/ROE/自由現金流

**改了什麼：**
清單第 3 項。驗證過 `TaiwanStockFinancialStatements`（免費，直接有 `EPS`/`Revenue`/`GrossProfit`/`OperatingIncome` 等欄位，不用自己算）、`TaiwanStockBalanceSheet`（免費，有 `EquityAttributableToOwnersOfParent` 給 ROE 分母）、`TaiwanStockCashFlowsStatement`（免費，有 `CashFlowsFromOperatingActivities` 和資本支出 `PropertyAndPlantAndEquipment` 可算自由現金流）都可用後接上個股頁「財報」分頁：
- 季度獲利 EPS 長條圖：近 8 季真實 EPS（用 `fyq()` 把日期轉成「26Q2」這種台股慣用格式）。
- 毛利率／營益率：最新一季 `GrossProfit/Revenue`、`OperatingIncome/Revenue`。
- ROE（近四季）：近 4 季歸屬母公司淨利加總 ÷ 最新一期歸屬母公司權益。
- 自由現金流（最新季）：營業現金流 + 資本支出（原始資料本來就是負值）。
- 卡片底下的來源說明**主動標註**「僅為期末日資料，非公告日，可能早於實際公告時間」——這是直接把里程碑 1（`research/DATA.md`）發現的 point-in-time 缺陷回饋進 App 本身，對使用者誠實揭露資料限制，不是只寫在內部研究文件裡。

**為什麼：**
使用者要求財報分頁如果 FinMind 有真實資料就換掉示範數字，一樣要求先驗證。

**影響到哪些檔案：**
只改 `alpha-app/index.html`。新增 `pivotByDate()`（把 FinMind 那種「一列一個科目」的長表轉成「一列一季」的寬表）、`fyq()`、`loadFinancials()`；`openStock()` 的 TW 分支呼叫它（不放進原本的 `Promise.all` 裡，讓財報分頁自己非同步載入、不拖慢總覽/營收的顯示速度），US 分支則把財報相關欄位設成「美股尚未支援」。

**測試方式：**
本機伺服器 + Chrome，開台積電財報分頁確認 EPS 長條圖（12.6 → 27.3，8 季）、毛利率 67.7%、營益率 60.3%、ROE +34.8%、自由現金流 +NT$6,356億，數字量級都合理（台積電高毛利/高ROE體質）。開 AAPL 財報分頁確認美股分支正確顯示「尚未支援」。Console 無錯誤。

**下一步：**
清單第 4 項——小幅體驗優化（載入中/錯誤狀態、FinMind 快取、修掉殘留假數字）。目前「今日」頁的大盤速覽（加權指數/台指期近月/NASDAQ）、市場頁 AI 卡、交易/日誌頁都還是原型示範資料，可以列入這項的候選。

**卡住的問題：**
無。

---

## 2026-08-22 02:10 — 新增 `research/` 資料夾：Phase 2 交易引擎的研究憲法與里程碑 1

**改了什麼：**
使用者貼了一份提煉自另一個加密貨幣量化機器人（Cybex）半年開發經驗的建議報告，存成 `research/CONSTITUTION.md`，訂為本專案 Phase 2（自動下單引擎）**所有策略研究都必須遵守的最高原則**——尤其是驗證紀律（holdout 物理隔離、隨機控制組、事前綁定通過標準）跟股票/加密貨幣本質差異那節。接著依使用者指定的里程碑順序（「地基先行」，嚴禁在驗證框架蓋好前挖策略），做完了**里程碑 1：資料誠實度盤點**，結果寫在 `research/DATA.md`，日誌記在 `research/STRATEGY_LOG.md`。

這一整塊是**純研究與文件**，完全沒有寫任何下單/回測程式碼，也沒有動 `alpha-data`。

**里程碑 1 三個重點發現：**
1. 台股還原股價（除權息調整）FinMind 免費方案沒有，是付費資料集；美股反而免費就有還原股價。
2. 下市股名單免費且完整，但歷史價格只有約 2003 年後下市的才查得到。
3. **最危險**：台股季報財務資料完全沒有公告日期欄位，只有財報期間的期末日——直接拿來當「已知日」會有嚴重的未來函數（提早 1.5 個月知道財報）。

**影響到哪些檔案：**
新增 `research/CONSTITUTION.md`、`research/DATA.md`、`research/STRATEGY_LOG.md`，都在 `alpha-app` repo 內。沒有動到 `alpha-app` 的 App 程式碼（index.html 等）或 `alpha-data`。

**需要使用者決定（寫在 `research/STRATEGY_LOG.md` 底部，詳見那邊）：**
里程碑 2（驗證框架）跟里程碑 3（紙上前測）要開始寫 Python 程式碼了，需要使用者決定這個研究/回測管線要放在哪個目錄／要不要開新 repo——`alpha-data` 是凍結區不能放，`alpha-app` 目前是純前端 repo。在使用者回覆前，先繼續其他可以自主進行的工作（App 前端清單），不會卡住等待。

**下一步：**
1. 繼續 App 前端清單第 3 項（個股財報分頁接真實 EPS）。
2. 等使用者決定研究管線放哪裡後，才會開始里程碑 2（驗證框架）的程式碼實作；在那之前不會挖任何策略。

**卡住的問題：**
無（上面的「需要使用者決定」不會卡住其他工作，只是暫停在那個特定分支）。

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
