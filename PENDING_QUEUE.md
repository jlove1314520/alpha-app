# PENDING_QUEUE.md — 待處理指令佇列

**這份檔案存在的理由**：使用者2026-09-01裁示的插隊保護升級規則——當你正在
執行一條指令、又收到新指令時，預設不立即切換，先把當前這條完整做完（含
驗證+commit），期間收到的新指令原封不動抄進這裡排隊，不省略、不摘要、
不改寫使用者原話。當前做完後，依「收到順序」一條一條做，做完一條就從
這裡劃掉（見 `CLAUDE.md` 第三節）。

**唯一的例外**：新訊息明確是「停/中斷/這個做錯了/先別做X」這類修正或
喊停指令——這種立刻處理，不進這裡排隊。

**格式**：每條待辦包含收到時間戳（或當時脈絡）+使用者原話全文，做完後
標記完成或直接從清單刪除。

---

## P0一（2026-09-03，「緊急P0：手機報價顯示昨天舊資料」）——**已被下面
P0二/P0三的更精確診斷取代，這一版的假設（SW快取問題）不成立，不再單獨
執行，保留原文只為紀錄軌跡**

原始指令全文：

> 全程繁體中文。緊急 P0：使用者手機上報價顯示昨天的舊資料，但 repo 裡台股是今天(13:30, 2330=2390)的——判定是手機快取吃到舊版。append PENDING_QUEUE 最優先做：
>
> 一、Service Worker 徹底不快取報價與 app-shell 過期問題：
> 1. 對所有報價 JSON（quotes_sinopac / quotes_ibkr / market 等）強制 network-first 且 no-store，確認 SW fetch handler 沒有對這些檔走 cache-first。
> 2. app-shell（index.html / JS）更新：SW 版本號 bump，加 skipWaiting() + clients.claim()，讓使用者一開 App 就拿到新版、不必手動清快取。
> 3. 用 Playwright 模擬「舊快取存在 → 開 App」情境，驗證會自動抓到最新報價 JSON，不是沿用舊的。
>
> 二、每個價格旁顯示「資料時間戳」（例：資料時間 09-03 13:30），讓任何過期一眼看穿——這是誠實標示、也讓使用者能自己判斷新舊。收盤後台股標「今日收盤」，不要繼續標「即時」。
>
> 三、確認報價排程真的在跑：檢查台股/美股報價任務的實際執行紀錄，美股 quotes_ibkr 停在 09-02 23:25、沒跑完整場美股時段，回報為什麼沒持續更新、以及排程(schtasks)到底建了沒、有沒有在跑。這關係到資料會不會自動更新，不是只有手機快取。
>
> 做完各自 Playwright 截圖 + smoke test 驗證，回報。

## P0二（2026-09-03，「緊急P0，插到PENDING_QUEUE最前面」——更精確診斷，
指出是接錯欄位不是快取）——**部分內容已被P0三取代（P0三發現真正根因是
20分鐘閘門+commit洪水，不是接錯欄位），P0二裡「加smoke test/全App掃一遍」
的要求仍然有效，併入P0三一起做**

原始指令全文：

> 全程繁體中文。緊急 P0，插到 PENDING_QUEUE 最前面，做完手上這一步就接。
>
> 【症狀】使用者手機 App 首頁「自選股」卡的 2330 顯示 2385（昨天收盤）。但 data/quotes_sinopac.json 裡 2330 是 last=2390（今天 09-03 13:30 tick 收盤）、prev_close=2385。結論：自選股卡沒用 Shioaji tick 的 last，而是顯示了 prev_close 或舊的 EOD 日線收盤。這是接錯欄位/接錯資料源，不是快取。
>
> 【修法】
> 1. 找到自選股卡（#wl-list，hydrateHome / 自選股渲染函式）的價格來源，回報它現在到底讀哪個檔、哪個欄位（quotes_sinopac.last？prev_close？還是 market/日線的最後一筆？）。
> 2. 改成：顯示價一律優先用 Shioaji tick 的 last（有值就用）；只有 tick 無值時才回退 EOD 日線收盤。不准再拿 prev_close 當現價。
> 3. 標籤誠實：盤中標「即時(tick)」；收盤後標「今日收盤」；回退到 EOD 時標「日線收盤（T-1）」並顯示該筆資料日期。每個價格旁顯示資料時間戳，讓過期一眼看穿。
> 4. 順便查 EOD 日線管線：為什麼收盤後 3 小時了日線還停在 09-02？回報排程時間並提案（先報不改）該不該提前到收盤後即跑。
> 5. 加 smoke test：「自選股卡每檔顯示價 == quotes_sinopac 對應 last（當 last 有值時）」，不相等即 FAIL，讓這個 bug 以後無法無聲復發。
> 6. 全部 App 上其他顯示現價的地方（市場頁、個股頁、交易頁）用同一條規則全面掃一遍，回報有沒有同樣接到 prev_close/EOD 的。
>
> Playwright 截圖驗證自選股卡確實顯示 2390（或當時的 last），smoke test 通過後回報。

## P0三（2026-09-03，最終且最完整的P0診斷——**正在執行中，以這版為準**）

原始指令全文：

> 全程繁體中文。以下為總司令核准的 P0 緊急修復，插到 PENDING_QUEUE 最前面依序做，每項各自 Playwright 截圖 + smoke test。
>
> 一、止血：tick 推送洪水（今天 995 commit，餓死 Actions）
> 1. research/shioaji_quotes.py tick 程式：本機逐筆訂閱不變，但 commit+push 改為「最多每 60 秒一次、且只在任一報價值有變時」。總司令已核准此頻率調整，不需再提案。
> 2. 兩支 workflow（quotes.yml / market.yml）的 push 重試：改成「先等 30 秒讓 in-flight push 落地再 fetch+rebase」、重試上限提到 10 次，避免再被餓死。
> 3. 回報今天各排程實際成功落地次數（quotes_tw / market_tw），並手動 workflow_dispatch 補跑一次讓今天的日線與大盤資料落地。
>
> 二、修根因：收盤後今天的收盤價被 20 分鐘閘門丟掉（index.html 1383、1798–1805）
> 1. sinopacQuote()/ibkrQuote()：當報價檔 market_status 為 closed、且該筆 tick 的成交時間屬於「當日」，一律接受為「今日收盤」，不套 INTRADAY_STALE_MIN；20 分鐘閘門只在盤中生效。
> 2. 標籤：盤中「即時(tick)」；收盤後「今日收盤 MM-DD」；真的退回 EOD 日線時標「日線收盤 T-1（MM-DD）」。每個價格旁顯示資料日期。
> 3. 全 App 掃一遍所有顯示現價的地方（首頁自選股、市場頁、個股頁、交易頁、籌碼頁）套同一規則。
> 4. 加 smoke test：「收盤後自選股每檔顯示價 == quotes_sinopac 對應 last」不等即 FAIL。
>
> 三、監控補洞（讓這種事以後自己叫出來）
> 1. data/STATUS.json：每個排程跑完必寫 last_run/last_status；新增「排程錯過時窗」判定（例：台股盤中 quotes 超過 30 分鐘沒落地 = 異常）。
> 2. App 設定頁顯示各資料檔的「最後更新時間 + 是否逾期」，逾期標紅。
> 3. 給 7 個沒有時間戳的資料檔（company_info / fundamentals / margin_maintenance / picks_ledger / price_history / quotes_all_tw / stock_detail）補 generated_at + source。
> 4. package.json 的 test 接上 node scripts/smoke_test.mjs。
>
> 四、結構解法只提案、先不做（需總司令核准）：寫一份簡短提案比較 (A) 報價 JSON 改推獨立 live-data 分支、amend+force 維持單一 commit，main 不再被洪水淹；(B) 直接把 B20 雲端中繼提前為下一步。各列工程量、風險、對手機即時度的影響，等總司令選。
>
> 五、restate 三軌馬拉松的暫停規則：把「選項(a)/(b)」原文與 PORTFOLIO_STRATEGY_SPEC.md 待確認的具體內容整理成一段給總司令看，先不動馬拉松，等裁示。
>
> 做完回報，附今天各排程落地次數與 smoke test 結果。

- [x] **P0三-一.1** shioaji_quotes.py commit洪水止血——**已完成**：根因
  是`_write_market_closed()`每次都更新`checked_at`寫進git追蹤檔案，
  讓外層`.ps1`的`git diff --quiet`永遠判定「有變動」，2分鐘排程*24小時
  不間斷commit。已修正：狀態未變完全不寫檔；`FLUSH_INTERVAL_SEC`調到
  60秒；新增`_meaningful_quotes()`只比較last/change_pct/bid/ask決定
  要不要commit，排除tick_at/volume這些會讓判斷永遠為真的欄位。8項
  單元測試全PASS（含2項新回歸測試），commit `8f14332`已push。
- [x] **P0三-一.2** quotes.yml/market.yml的push重試改善——**已改好，但
  只能留在working tree（PAT無workflow scope，commit會被GitHub拒收）**：
  第一次push前先fetch+rebase、每次失敗先等30秒再fetch+rebase、重試上限
  5→10次；另外加了`timeout-minutes`（quotes 15分鐘／market 120分鐘，理由
  見一.3）跟market.yml commit前重跑`generate_status_json.py`的步驟。
  **需要使用者自己用有workflow scope的PAT把這兩個檔案的改動commit上去**
  （`git add .github/workflows && git commit && git push`），或在GitHub網頁
  直接貼上。
- [x] **P0三-一.3** 落地次數已查明（2026-09-03台北日）：quotes.yml觸發5次、
  **成功落地0次**（4次被concurrency group cancelled、1次`run 33754429235`
  從12:18Z卡在「抓台股盤中報價」步驟超過3.5小時仍in_progress），
  `data/quotes_tw.json`當天0次commit、最後一筆停在09-02；market.yml觸發
  1次成功（11:07Z，`market_tw.json`當天2次commit，19:46台北落地，當天
  日線/大盤資料**已經落地，不需要再補跑**）。**卡死根因**：scores.json改
  全市場宇宙後有18,804列（16,453列是6位數權證），fetch_quotes_tw.py把整份
  當查詢清單→一次查2,352檔、sparkline逐檔打STOCK_DAY每檔吃滿15秒timeout
  →數小時，MIS偶發502又讓整支炸掉。已修：範圍回到檔頭原本定義（自選股+
  三榜各前100名、過濾權證/特別股，共209檔）、MIS批次失敗重試再跳過、
  sparkline 240秒總預算+連續8檔失敗斷路（commit `51ff9e7`）。
  **workflow_dispatch補跑與取消卡住的run都做不到**：這個PAT對Actions API
  回403「Resource not accessible by personal access token」，需要使用者
  在GitHub網頁操作：(1) Actions→該run→Cancel workflow（不取消的話會佔到
  6小時上限、約02:18台北自動timeout）；(2) Actions→「盤中近即時報價」→
  Run workflow。本機直接跑腳本補落地也試過：MIS在深夜（23:5x）對所有
  批次回`RemoteDisconnected`，是TWSE端夜間不服務，非程式問題。
- [x] **P0三-二** 修根因：20分鐘閘門在收盤後誤丟今日收盤價——**已完成**：
  根因是`sinopacQuote()`/`ibkrQuote()`對`connected`/20分鐘閘門不分盤中
  盤後一律套用，收盤後`connected`變`false`直接return null，整條intraday
  資料被略過，退回完全不同管線的prev_close/EOD。新增`_shouldTreatAsLive()`
  優先信任後端`market_status`欄位、`_intradaySourceFresh()`統一套用到
  四處（自選股/個股頁頭部/市場頁大盤指數/市場頁期貨/市場頁美股指數）。
  個股頁頭部價格原本完全沒接Shioaji/IBKR即時報價，這次一併接上。
  smoke check 23（收盤後顯示價==quotes_sinopac的last）+ check 22修正，
  23項全PASS，Playwright截圖確認2330正確顯示2390+「今日收盤」badge。
  commit `420914a`已push。**交易頁/籌碼頁查證後沒有這個bug模式**（交易頁
  是demo假資料或走IBKR order server帳戶摘要，籌碼頁是三大法人/融資
  彙總數字，都不經過sinopacQuote()/ibkrQuote()這條路徑）。
- [x] **P0三-三** 監控補洞——**已完成**（commit `51ff9e7`+`93b0898`）：
  (1) `generate_status_json.py`新增`schedule_health`（盤中30分鐘／每日排程
  寬限3小時的「錯過時窗」判定，11個監控項）與`workflows[].today_runs`
  （今天各結論次數）；「每個排程跑完必寫」那半段靠market.yml新增的
  generate_status_json步驟（見一.2，待使用者commit workflow）；(2) App
  設定頁新增「資料新鮮度」卡片，13個資料檔各一列，逾期/無資料紅字、正常
  綠字，手機端「現在」直接算不依賴STATUS.json（三個超大檔例外，讀STATUS.json
  並註明）；(3) 7個資料檔的產生腳本都補`meta.generated_at`+`source`
  （margin_maintenance頂層是list，寫進每筆record不改形狀；company_info既有
  檔以git commit時間回填並在`generated_at_note`註明不是重新產生）；(4)
  `package.json` test→`node scripts/smoke_test.mjs`。smoke test新增檢查24，
  22項全PASS；Playwright截圖確認4項逾期紅字正確。
- [x] **P0三-四** ——**已被「乙」取代，不再另寫提案**：總司令已核准Phase 1
  冷熱分離（盤中不push、本機live server+Cloudflare Tunnel），這條路直接讓
  main不再被洪水淹，(A)live-data分支／(B)B20提前兩案要解的問題已由乙的
  裁示解掉。
- [x] **P0三-五** ——**已被「甲」取代**：總司令已裁示「確認SPEC＋解除暫停」，
  不需要再整理選項(a)/(b)給總司令選。

---

## HTTPS方案A（2026-09-04下午，總司令裁示，使用者原話全文，收到時正在查P0帳務問題，
依插隊保護規則先登記，帳務調查完成後接續本項）

原始指令全文：

> 全程繁體中文。總司令裁示方案 A：自簽憑證讓 alpha_live_server 走 HTTPS，解決 PWA（https://jlove1314520.github.io）抓 http://192.168.3.241:8001 的混合內容封鎖。分兩階段，第一階段先做、切換 HTTPS 等總司令確認手機已裝好憑證再做：
>
> 1. 產生根 CA（RSA 4096、SHA-256、10 年、CN=Alpha Local CA、CA:TRUE）與伺服器葉憑證（RSA 2048、由 CA 簽、有效期 ≤825 天——iOS 硬性上限、SAN 含 IP:192.168.3.241 與 IP:127.0.0.1、DNS:localhost、EKU=serverAuth）。私鑰放 secrets/ 絕不進 repo；CA 公開憑證另存 DER 格式 alpha-ca.crt。
> 2. 在目前 HTTP 的 alpha_live_server 加 GET /ca.crt 回傳 alpha-ca.crt（Content-Type: application/x-x509-ca-cert），此端點不需 token。
> 3. 第二階段程式先寫好不切換：uvicorn --ssl-keyfile/--ssl-certfile 於 8001；CORS 已有，確認 allow_headers 含 X-Alpha-Local-Token、OPTIONS preflight 不驗 token；Playwright 對自簽加 ignoreHTTPSErrors。
> 4. 回報 /ca.crt 可從 http://192.168.3.241:8001/ca.crt 下載、憑證 SAN/有效期，等總司令說「手機裝好了」再切 HTTPS。

- [x] **HTTPS.一** ——**已完成**（commit `c640ee4`）：`research/gen_local_ca.py`（新增）產生根CA（RSA 4096/SHA-256/10年2036-09-01到期/CN=Alpha Local CA/CA:TRUE critical/keyUsage keyCertSign+cRLSign critical）與伺服器葉憑證（RSA 2048/由CA簽/825天2028-12-07到期/SAN=IP:192.168.3.241+IP:127.0.0.1+DNS:localhost/EKU serverAuth critical）。全部6個檔案輸出`secrets/`（私鑰`alpha-ca-key.pem`/`alpha-server-key.pem`絕不進repo，`git status`確認過secrets/沒出現在任何commit）；CA公開憑證DER格式`secrets/alpha-ca.crt`。
- [x] **HTTPS.二** ——**已完成**：`GET /ca.crt`回傳`secrets/alpha-ca.crt`（DER，`Content-Type: application/x-x509-ca-cert`），刻意不驗token（CA公開憑證本身不是機密，端點程式碼裡完全沒有讀取私鑰的路徑）。本機實測：無token下載200、與原始檔逐位元相同。
- [x] **HTTPS.三** ——**已完成，維持不切換**：`ENABLE_HTTPS`環境變數（`ALPHA_LIVE_SERVER_HTTPS=1`）控制`uvicorn.run()`要不要帶`ssl_keyfile`/`ssl_certfile`，**預設值是False，正式伺服器目前仍是HTTP**（`/health`回`https_enabled:false`確認）；CORS `allow_headers=["*"]`已涵蓋`X-Alpha-Local-Token`（加註解講清楚不留疑問）；OPTIONS preflight本來就不經過`_check_token()`（Starlette CORSMiddleware框架行為，實測回200）；`scripts/smoke_test.mjs`加`ignoreHTTPSErrors:true`（目前no-op）。**獨立測試埠8013**開`ENABLE_HTTPS=1`驗證整條HTTPS路徑本身正常：`openssl s_client -verify_return_error`回`Verify return code: 0 (ok)`、Python `requests`用CA pem驗證成功200——**憑證鏈本身完全正確**（Windows版curl因schannel強制檢查憑證撤銷狀態、私有CA沒有撤銷基礎設施而報錯，這是curl-for-Windows已知限制不是憑證問題，已用openssl/requests交叉驗證排除）。smoke test 32項全PASS、單元測試13項全PASS，正式伺服器未受影響。
- [x] **HTTPS.四** ——**已完成（2026-09-05 10:26，總司令確認手機已安裝Alpha Local CA並完全信任後切換）**：`C:lpha
un-alpha-live-server-cycle.ps1`加`$env:ALPHA_LIVE_SERVER_HTTPS="1"`（常駐/開機路徑都走這支，重開機後仍是HTTPS）；重啟後`netstat`確認`0.0.0.0:8001 LISTENING`（PID 61172）、啟動log印「HTTPS模式啟用」。本機驗證：`http://192.168.3.241:8001/health`已連不上（000，HTTP已關）；`curl -k https://192.168.3.241:8001/live/quotes`→401、帶token→200；`https://…/ca.crt`→200且與secrets/alpha-ca.crt一致；Python requests用CA pem驗證→200、`openssl s_client`→`Verify return code: 0 (ok)`。CORS：allow_origins含`https://jlove1314520.github.io`、preflight回`access-control-allow-headers: X-Alpha-Local-Token`、OPTIONS無token→200。**總司令需把App設定頁伺服器網址從`http://192.168.3.241:8001`改成`https://192.168.3.241:8001`。**

---

## P0帳務完整性（2026-09-04下午，總司令實測，使用者原話全文，插最前面）

原始指令全文：

> 全程繁體中文。P0 帳務完整性問題（總司令實測發現）：交易紀錄有多筆出場但「已實現損益」恆為 0。
>
> 一、根因查證與修正：
> 1. 09-01 標「補記」的交易，進場價＝出場價（WAL 0.02489/0.02489、TRX 0.3223/0.3223…），是回補時真實進場價遺失、用出場價佔位。這違反假資料零容忍。修法：從交易所成交紀錄（fills / order history API，免費）重建真實進場價與時間；重建不到的，該筆標「進場價不明」並**排除**在已實現之外、UI 明顯標示，禁止再用佔位價。
> 2. 損益欄位現在顯示的是「波段高回落幅度」不是損益，欄位標錯。損益欄只放依真實進場計算的已實現 $ 與 %；波段高/吐回另立欄位並命名清楚。
> 3. 已實現損益改為由配對成交（FIFO）推導，不得依賴手寫或佔位。
>
> 二、把帳務恆等式做成每日自動對帳（防「沒看到的一堆」）：
>    (a) 現金 + Σ(持倉數量×市價) = 權益；
>    (b) Σ已實現(已平倉) + Σ未實現(未平倉) = 權益 − 初始本金 − 出入金；
>    (c) 每筆出場必須配對到一筆進場，且進場價、時間為真實成交，不得與出場同價同時（除非成交紀錄證明）；
>    (d) 「補記」列必須帶交易所成交 id 來源，否則排除並標示。
>    任一恆等式不成立 → 儀表板頂端紅色橫幅列出差額與哪一條壞了，並禁止標「已實現」數字為綠色正常。
>
> 三、修完回報：重建成功幾筆、排除幾筆、對帳四條目前是否全部成立、修正前後已實現數字。

- [x] **帳務全項** ——**已跟總司令確認並改路線，不在本session（Alpha）處理**：查證發現這批交易（WAL/TRX等）的程式碼不在`C:\alpha`，是完全獨立的Cybex交易系統，位於`C:\Users\user\AppData\Roaming\Claude\local-agent-mode-sessions\...\outputs\research`，有自己的33KB `CLAUDE.md`規則、1.5MB `REPORT.md`、獨立桌面捷徑「Cybex Claude Code」會開專屬session。已用AskUserQuestion請示，總司令裁示**改用Cybex專屬session處理**。這裡查到`ListAgents`目前跟Cybex相關的是`research-a6`（busy，可能是它的挖礦馬拉松）跟`Cybex挖礦終端機`（Remote Control，offline）——沒有現成idle的Cybex session可以直接轉交，總司令需自己雙擊桌面「Cybex Claude Code」捷徑或等`research-a6`空出來，把這條P0帳務指令貼過去給那個session執行。**此條目在Alpha這邊不再繼續，僅留紀錄。**

---

## Cloudflare 網域上線準備（2026-09-06，總司令指令原話全文，今晚執行，插最前面）

原始指令全文：

> 全程繁體中文。總司令已同意購買網域走 Cloudflare Public Hostname（今晚執行），請先把伺服器端準備好，網域一到手就能切：
>
> 1. cloudflared 設定：預備 Public Hostname 的 ingress 規則，把 live.<domain> 轉到本機 live server。live server 目前是自簽 HTTPS 於 8001，cloudflared 連它要設 originRequest.noTLSVerify=true（或另開一個僅供 cloudflared 使用的本機 HTTP 監聽），選一種並說明理由。
> 2. CORS：allow_origins 保留 https://jlove1314520.github.io；因為之後 Cloudflare Access 會擋在前面，前端 fetch 需帶 credentials，伺服器要回 Access-Control-Allow-Credentials: true 且 Allow-Origin 用精確來源（不可用 *）。
> 3. Cloudflare Access 與跨來源 fetch 的相容：研究並回報 Access application 的 CORS 設定要怎麼填（允許來源 github.io、允許 credentials、允許 X-Alpha-Local-Token 標頭），以及 PWA 是否需要先在瀏覽器開一次 live.<domain> 建立 Access 登入 cookie。寫成總司令今晚可照做的步驟。
> 4. App 設定頁「伺服器網址」欄位要能接受網域形式（https://live.xxx），並在切換後自動重新測試連線。
> 5. 加分項（可選）：GitHub Pages 支援免費自訂網域——評估把 App 也放到 app.<domain>，與 live.<domain> 同站，cookie 與 CORS 都更簡單；先評估不要動。
> 6. 多裝置同步 /settings 端點照佇列進行，網域切好後公司手機就能用。
>
> 回報：ingress 規則草稿、CORS 修改、Access CORS 步驟說明。

**排序說明**：這條是後到的，但總司令指名「先把伺服器端準備好」且網域今晚就要切，
所以排在稽核.二之前執行，做完立刻回頭做稽核.二，不跳過。

- [x] **CF.1** **已完成**：`cloudflared/config.example.yml`。選第三條路 caPool + originServerName=localhost（完整驗證、伺服器零改動）；不選另開 HTTP 監聽是因為同行程已綁 UDP 8002，第二個 uvicorn 會 bind 失敗；noTLSVerify 保留為備援。
- [x] **CF.2** **已完成**：明確來源清單＋`ALPHA_LIVE_ALLOW_ORIGINS` 環境變數擴充、`allow_credentials=True`、allow_headers 明列並含 CF-Access 兩標頭、`/health` 揭露 cors 設定。實測預檢 github.io=200／白名單外=400。
- [x] **CF.3** **已完成**：`docs/cloudflare_tunnel_setup.md`。查出 Access 預檢必 403（瀏覽器不在 OPTIONS 帶 cookie）需開 Bypass OPTIONS，且 iOS Safari 會擋 github.io→新網域的跨站 cookie，因此建議改走 Access 服務權杖；App 已加兩個選填欄位。
- [x] **CF.4** **已完成**：`normalizeLiveUrl()` 自動補 scheme／去尾斜線與路徑（私有 IP 補 http），存檔後自動 `testLiveConnection()`。
- [x] **CF.5** **已評估未執行**：技術可行、cookie 與 CORS 會簡單很多，但換來源會讓已安裝的 PWA 失效且 localStorage（自選股/設定）全部不見。建議等 /settings 多裝置同步上線後再搬。
- [ ] **CF.6** /settings 多裝置同步（同稽核.四）

---

## 稽核.二（2026-09-06，總司令指令原話全文）

原始指令全文：

> 全程繁體中文。稽核.一完成得很好，接續稽核.二，優先序依稽核報告：
>
> 一、季報斷層 597 檔（P0，這是「財報成長」「估值」兩因子算錯的源頭）
> 1. 查證：stock_detail 為何缺 2025Q1～2026Q1 五季——是那段時間排程沒跑、MOPS 抓取失敗、還是解析失敗？回報根因。
> 2. 從 MOPS（公開資訊觀測站）財報全部回補該五季，含損益表與資產負債表主要欄位；回補後重跑 e_quarters_gap/e_quarters_stale 稽核，兩項違規數必須歸零或列出「官方確無此季」的例外清單。
> 3. 回補完重算八因子分數，回報全市場完整度中位數與 <60% 檔數的變化。
>
> 二、coverage.json 覆蓋率儀表板：八因子 × 全市場，每因子覆蓋率%、缺漏檔數、缺漏原因四分類；設定頁顯示。稽核報告的 completeness_gap 與這張表要對得起來。
>
> 三、鑫永洋 6241 本益比 22.64 vs 35.64：查是哪邊算錯，修正並確認同類計算全市場一致。
>
> 四、稽核排程：data_audit.py 每晚收盤後自動跑、audit_report.json 顯示於設定頁「資料健康」；違規率 >1% 或 code_free_violations >0 時 smoke test FAIL。
>
> 五、其餘佇列照序：多裝置 /settings、自建資料庫每日累積、柱狀圖零基線、融資維持率分母、休市標籤、群益唯讀、分點演習、產業價值鏈、新聞管線、本地摘要。每完成一項回報一項附證據。

- [ ] **稽核二.一** 季報斷層根因＋MOPS 回補五季＋重跑稽核＋重算八因子回報完整度變化
- [ ] **稽核二.二** data/coverage.json 八因子覆蓋率儀表板＋設定頁顯示，與 completeness_gap 對得起來
- [ ] **稽核二.三** 鑫永洋 6241 本益比 22.64 vs 35.64 根因與全市場一致性
- [ ] **稽核二.四** 稽核每晚排程＋設定頁資料健康＋smoke FAIL 條件（設定頁與 smoke 已於稽核.一完成，缺排程落地）
- [ ] **稽核二.五** 其餘佇列照序

---

## P0 資料一致性（2026-09-06，總司令實測「光聖6442現價1755、建議進場價32」，使用者原話全文，插最前面）

原始指令全文：

> 全程繁體中文。總司令實測：光聖 6442 現價 1755、建議進場價卻顯示 32。這是「一類錯誤」，不修單檔，做結構性防線。插 PENDING_QUEUE 最前面。
>
> 一、全市場資料一致性稽核（P0，今天就要有第一份報告）
> 1. 新增 scripts/data_audit.py，對全部 2,837 檔逐檔檢查恆等式，任一違反即記錄：
>    (a) 所有頁面顯示的「現價」必須來自同一個 canonical 來源（優先 live → quotes_tw → price_history 最後收盤），不得各頁各讀；
>    (b) 建議進場價/分批價必須在現價 ±30% 內；
>    (c) 20 日低點 ≤ 現價 ≤ 20 日高點（允許當日突破 5%）；
>    (d) 市值 ≈ 現價 × 流通股數（誤差 <5%）；
>    (e) 月營收年增、EPS、本益比彼此不得矛盾（例：本益比 = 現價/EPS 誤差 <10%）；
>    (f) 任何數值欄位不得為 NaN/None 卻在 UI 顯示為數字；
>    (g) 千分位逗號解析：掃所有抓取器（不只 STOCK_DAY），凡用 float() 直接轉 TWSE/TPEx 字串的一律改為去逗號解析——光聖的 32 極可能就是同一個 bug 在另一支抓取器裡。
> 2. 先查光聖 6442 的 32 到底從哪個欄位、哪個檔來，回報根因。
> 3. 稽核每晚排程跑，輸出 data/audit_report.json；違規檔數與清單顯示在 App 設定頁「資料健康」區；違規率 >1% 時 smoke test FAIL、禁止 commit 到 main。
> 4. 第一份全市場稽核報告今天出，附違規總數與前 20 筆。
>
> 二、因子覆蓋率儀表板＋補齊
> 1. 產出 data/coverage.json：八因子 × 全市場，每因子覆蓋率%、缺漏檔數、缺漏原因分類（新上市不足一季／官方無此資料／抓取失敗／解析失敗）。
> 2. 「抓取失敗」「解析失敗」兩類今天全部補齊；「官方無此資料」列清單回報；「新上市」明標。
> 3. 設定頁顯示覆蓋率儀表板，總司令能一眼看到還缺哪裡。
>
> 三、自建全市場資料庫（成為資料方而非買方的基礎）
> 每日一次、零額外成本，把以下免費官方資料集全部累積進 data/ 歷史（append，不覆蓋）：TWSE/TPEx 每檔三大法人、融資融券、借券、當沖比、外資持股比、集保股權分散（週）、月營收（MOPS）、季財報（MOPS）、除權息、重大訊息。每個資料集記錄來源、抓取時間、涵蓋率。目標：六個月後擁有可自用亦可衍生商品化的完整資料庫。原始交易所資料不得對外轉售，衍生訊號可。
>
> 四、多裝置同步：live server 新增 /settings 端點（token 驗證），儲存自選股、幣別、風控參數；App 啟動時拉取、變更時推送，讓任何裝置設定一致。等總司令買好網域切 Public Hostname 後，公司手機也能用。
>
> 五、其餘佇列項目照序繼續（柱狀圖零基線、融資維持率分母、休市標籤、群益唯讀、分點演習、產業價值鏈、新聞管線、本地摘要）。每完成一項回報一項附證據。

- [x] **稽核.一** **已完成**：6442 的 32 根因＝報告頁 `peg=null` 讓 renderReport 中途拋錯、上一檔（6808，收盤 32.0）的分批進場價留在畫面上（三個數字逐一吻合，已用 Playwright 重現）。四層防線：缺值安全格式化、REPORT_SEQ 世代守衛、面板 _safeSync 隔離＋進場清空、canonicalPrice ±30% 恆等式。`scripts/data_audit.py` 七類恆等式已產出首份全市場報告（2104 檔、一致性違規率 0.05%、通過 1% 門檻；完整度缺口 52.33% 歸稽核.二）。過程另抓到 **161 檔已下市股票還在選股榜上**（未來成長榜第 1 名是造假下市的康友-KY 6452），新增 build_listed_universe.py / prune_delisted.py 並在 generate_scores_live.py 加同一道過濾。設定頁新增「資料健康」區；冒煙測試新增 39/40/41 三道閘門，39 項全 PASS。⚠ `.github/workflows/audit.yml` 因 PAT 無 workflow scope 留在 working tree。
- [ ] **稽核.二** data/coverage.json 八因子覆蓋率儀表板＋補齊「抓取失敗/解析失敗」兩類
- [ ] **稽核.三** 自建全市場資料庫（每日append累積10類官方資料集）
- [ ] **稽核.四** live server /settings 端點多裝置同步
- [ ] **稽核.五** 其餘佇列照序

---

## 總司令三項補充（2026-09-05，使用者原話全文，插最前面）

原始指令全文：

> 全程繁體中文。總司令三項補充，插 PENDING_QUEUE 最前面，排序照末尾。
>
> 零、全市場歷史價與走勢線（取代「自選股逐檔抓 20 日」的錯誤模式）
> 1. 改為每日一次全市場抓取：TWSE STOCK_DAY_ALL（全上市當日 OHLCV）＋ TPEx 上櫃全市場日成交檔，各一次請求，append 進 price_history；含千元以上股票的逗號解析修正與歷史回補。
> 2. 走勢線不再逐檔抓：由 price_history 預先產出全市場 sparklines.json（每檔近 20 收盤，小檔），App 任何頁面、任何新加入的股票一律讀這個檔。
> 3. 閘門：price_history 覆蓋率 ≥ 全市場上市＋上櫃 95%，並列出缺漏清單與原因；「有 ≥2 筆歷史價卻無線」＝FAIL。
> 4. 回報：修復前後覆蓋股票數、千元股回補結果。
>
> 零之二、分點資料沙盤演習（系統性掃描，只走官方 API）
> 1. 列出台灣所有可接的券商與資料商 API：群益、永豐 Shioaji、元大、凱基、國泰、統一、玉山、富果/籌碼K線、FinMind、CMoney、嘉實 XQ、證交所 OpenAPI、櫃買 OpenAPI、集保 OpenAPI。
> 2. 每家逐項查證並填矩陣：是否有公開 API／是否免費／申請條件／是否提供券商分點（逐檔逐券商買賣）／提供哪些籌碼類資料／測試或模擬環境有無。
> 3. 富果/籌碼K線：總司令有付費訂閱，請總司令登入富果開發者後台後由 CC 讀取該帳號實際開放的 API 產品與端點清單，不憑公開文件推論；有分點端點就用測試環境接上並回報資料格式。
> 4. 群益：一併在此演習中確認其 API 是否含分點類資料。
> 5. 有分點的管道：用測試/模擬環境接上，回報格式與費用；全部沒有就明講「唯一有分點的合法管道是 X（付費）」。
> 6. 鐵律：只走官方 API 與文件，不撈任何 App 後端、不繞 ToS。
>
> 零之三、產業地圖資料源
> 1. 接櫃買中心「產業價值鏈資訊平台」（ic.tpex.org.tw）：抓每個產業的上/中/下游分段與所屬公司，產出 industry_chain.json；先確認 robots 與使用條款允許程式抓取，不允許就回報。
> 2. 接 MOPS 公司基本資料（產業類別、主要經營業務），補齊 company_info 對上市＋上櫃全覆蓋，消滅所屬產業「—」。
> 3. 個股頁「所屬產業」改顯示：產業別＋價值鏈位置（上/中/下游）＋同鏈公司數；市場頁類股卡可點進看成員（B4）。
> 4. 這份 industry_chain.json 同時是 B9 供應鏈連動與題材對照表的基底。
>
> 執行順序：零 → 五（千元股修復已併入零）→ 一（八因子）→ 零之三（產業）→ 三（新聞管線）→ 零之二（分點演習）→ 二（群益唯讀）→ 四（本地摘要）→ 其餘。每完成一項回報一項，附證據。

**執行順序（總司令指定，已完成的標 [x]）**：
- [x] **零** 全市場歷史價與走勢線——**已完成**（commit `412154e`）：查明 `update_price_history.py` 本來就是全市場兩請求架構（TWSE STOCK_DAY_ALL + TPEx tpex_mainboard_quotes）；新增 `build_sparklines.py` 從 price_history 切出 `data/sparklines.json`（2827檔/286KB/零額外請求），App 統一讀它；`fetch_quotes_tw.py` 移除整段逐檔抓取與死碼（446→357行）。覆蓋率：官方上市 1094/1094=100%、上市+上櫃 2196/2210=99.4%（門檻95%）；上櫃高價股 5274 也有20點（舊架構永遠拿不到）。smoke check 38，36項全PASS。⚠ market.yml 的新步驟留在 working tree（PAT 無 workflow scope）。
- [x] **五.千元股** 已完成並併入零（commit `be17ee7`：`_num()` 千分位逗號根因＋5項回歸測試）
- [x] **一** 評分引擎八因子全部填上——**已完成**（commit `73bfb07`：覆蓋率中位數 0.42→0.74、
  <60% 82.3%→32.1%、7711 rank 1→44、2330 七項因子完整度92%、smoke 35項全PASS）
- [ ] **零之三** 產業地圖（ic.tpex.org.tw 價值鏈＋MOPS 補齊 company_info＋個股頁顯示價值鏈位置）
- [ ] **三** 免費第一手資料管線（MOPS/法說會/月營收/SEC 8-K/RSS → news.json/events.json，接因子五）
- [ ] **零之二** 分點資料沙盤演習（14家API矩陣＋富果後台實際端點＋群益確認，只走官方API）
- [ ] **二** 群益證券API唯讀先行（下單入口保持關閉、更新CONSTITUTION）
- [ ] **四** 本地AI摘要（GPU/記憶體確認→開源模型→法說會PDF摘要）
- [ ] **其餘** 三大法人柱狀圖零基線／融資維持率分母改MI_MARGN／週末標頭休市／移除未上線推播開關／
  唯讀持倉餘額經live server

---

## 總司令裁示修正與新增（2026-09-05，使用者原話全文，插最前面）
**取代上一版「週六實測九項」的第二項做法**：取消「完整度<60%不顯示分數」，改為補齊資料。
**回報紀律（硬性）**：做完一項立即回報一項；回報只能是「已完成／進行中（附進度%）／阻塞（附具體原因）」，
不准出現「下一輪」「兩週後」這類字眼。

原始指令全文：

> 全程繁體中文。總司令裁示修正與新增，插 PENDING_QUEUE 最前面。取消上一版「完整度<60%不顯示分數」的做法，改為補齊資料。時程一律「依序做、做完一項立即回報一項」，不准回報「下一輪」「兩週後」這類字眼——回報只能是已完成、進行中（附進度%）、或阻塞（附具體原因）。
>
> 一、評分引擎八因子全部填上（P0，接在千元股解析修復之後）
> 1. 財報成長：fundamentals.json 既有欄位（營收/毛利/營益/EPS 年增）。
> 2. 估值(成長調整)：本益比、股價淨值比、PEG，同產業百分位。
> 3. 技術型態：price_history 算 MA 多空排列、20/60 日相對位置、RSI、量能變化。
> 4. 機構觀點：台股無免費目標價，改用「投信/外資持股比例變化＋連續買賣天數」當機構行為因子，因子名稱與說明明標「機構行為（非分析師目標價）」。美股用 yfinance 目標價。
> 5. 題材/事件：接 MOPS 重大訊息＋月營收公布＋除權息事件，依事件類型與新鮮度計分；資料源本輪就建（見三）。
> 6. 每個因子的說明文字改為真實計算依據，刪除所有「需要新聞/供應鏈連動分析，下一輪實作」佔位字。
> 7. 完整度標示保留，但只有真的無資料（如新上市不足一季）才標「資料不足」；並保留極端走勢風險標示（60 日漲幅>80% 或營收年增觸硬上限）。
> 8. 驗收：全市場完整度分布（中位數、<60% 檔數）修改前後對照；永擎 7711 修改前後八因子逐項對照。
>
> 二、群益證券 API：唯讀先行＋分點演習
> 1. 查群益 API 官方文件，列出實際提供的資料功能（報價、K 線、帳務、持倉、以及是否有券商分點/買賣分點類資料），逐項回報，不預設有或沒有。
> 2. 接唯讀：登入、帳戶餘額、持倉、成交回報查詢。憑證與帳密放 .env/secrets/，絕不進 repo。
> 3. 分點演習：若 API 有分點類資料，用群益提供的模擬/測試環境接看看並回報格式；若沒有，誠實回報「群益 API 無分點端點」並列出它有的替代資料。
> 4. 鐵律：本階段不得呼叫任何下單函式；下單 adapter 骨架可以寫，但入口保持關閉，等總司令明確核准才開。Alpha 下單路徑規劃改為：台股下單→群益、報價→永豐；更新 CONSTITUTION.md。
>
> 三、免費第一手資料管線本輪就建（不是兩週後）
> MOPS 重大訊息＋法說會公告＋法說會簡報 PDF 連結＋月營收公布、SEC EDGAR 8-K、鉅亨/中央社/Yahoo RSS → news.json / events.json（只存標題、連結、時間、標的）。GitHub Actions 每 30 分鐘。做完立即接進評分因子五與個股頁事件分頁。
>
> 四、本地 AI 摘要（零 API 費）
> 在本機安裝開源模型執行環境與一個繁中能力好的開源模型（依電腦規格選 7B 級；先確認 GPU/記憶體再選），法說會 PDF 抽文字→本地模型摘要→存 summaries.json→個股頁顯示，標「本地模型摘要，非投資建議」。法說會影音用本機 Whisper 轉錄。先跑通一檔當驗證，再排程批次。
>
> 五、其餘沿用上一版：千元股解析修復與回補、三大法人柱狀圖零基線、融資維持率分母改 TWSE MI_MARGN、週末標頭「休市」、移除未上線功能的推播開關、唯讀持倉/餘額經 live server（改由群益資料供應）。
>
> 順序：五的千元股修復 → 一 → 三 → 二 → 四 → 五其餘。每完成一項回報一項，附證據。

**執行順序（依總司令指定）**：
- [x] **新五.千元股** 千元股解析修復與回補——**已完成，已回報**（commit `be17ee7`：根因是
  `fetch_quotes_tw.py::_num()` 裸 `float('2,410.00')`；附證據鏈、5項回歸測試、smoke check 35/36）
- [ ] **新一** 評分引擎八因子全部填上（財報成長／估值PEG／技術型態MA+RSI+量能／機構行為／題材事件／
  真實說明文字／完整度標示保留／驗收對照）
- [ ] **新三** 免費第一手資料管線（MOPS重大訊息+法說會+PDF連結+月營收、SEC 8-K、RSS → news.json/events.json，
  Actions每30分鐘，接進因子五與個股頁事件分頁）
- [ ] **新二** 群益證券API唯讀先行＋分點演習（查文件→接唯讀→分點演習→下單入口保持關閉、更新CONSTITUTION）
- [ ] **新四** 本地AI摘要（先確認GPU/記憶體→裝開源模型→法說會PDF摘要→summaries.json→個股頁）
- [ ] **新五其餘** 三大法人柱狀圖零基線／融資維持率分母改MI_MARGN／週末標頭休市／移除未上線推播開關／
  唯讀持倉餘額經live server（改由群益供應）

---

## 週六實測九項（2026-09-05，總司令實測，使用者原話全文，依嚴重度插最前面）

原始指令全文：

> 全程繁體中文。總司令週六實測九項，以下依嚴重度插 PENDING_QUEUE 最前面，每項附證據驗收：
>
> 一、資料完整性 P0：千元以上股票整條管線消失
> quotes_tw.json 中 2330/2454 sparkline_error='not_available:empty'，且 price_history.json 完全沒有 2330、2454。兩檔正好是自選股中唯二股價>1000 者。假設：TWSE STOCK_DAY 回傳帶千分位逗號的字串（"2,410.00"），解析失敗被當空值。
> 1. 用證據驗證：直接印出 TWSE STOCK_DAY 對 2330 的原始回應與解析結果，不准再猜快取/限流。
> 2. 修解析（去逗號後轉數值），回補 price_history 全部缺漏股票，回報回補前後股票數與缺漏清單。
> 3. 評估影響：這些股票在 scores.json/技術因子/回測宇宙裡是否也缺，逐一回報。
> 4. 閘門：check「price_history 必含 2330/2454/3008/5274」「自選股有 ≥2 筆歷史價卻無走勢線＝FAIL」。
>
> 二、評分引擎 P0：只算兩個因子卻顯示 9.9
> 1. 財報成長／估值(成長調整)／技術型態三個因子改接既有資料（fundamentals.json、price_history），不再標「需要新聞」。只有機構觀點（台股無免費源）與題材/事件（等 Phase 2）維持不計入，文字改為真實原因。
> 2. 資料完整度 <60% 的股票：不顯示綜合分圓環，改顯示「資料不足，暫不評分（完整度 X%）」，選股榜也不得排進前段。
> 3. 極端走勢防呆：60 日漲幅 >80% 或月營收年增觸硬上限者，個股頁頂端加風險標示，分批買入計畫改為不顯示。
> 4. 所屬產業「—」：查 company_info 對上櫃股的覆蓋，補齊。
>
> 三、三大法人柱狀圖：改零基線正負向（正值向上、負值向下、共用基線），加閘門「正值柱底 y 必須等於基線 y」。
>
> 四、融資維持率：分母改用 TWSE MI_MARGN 每日公布的全市場融資金額，拔掉最後一個 FinMind 依賴；回報前後數值差異。
>
> 五、券商唯讀資料經 live server：新增 /live/positions 與 /live/balance（Shioaji list_positions/account_balance、IBKR 部位），一律驗 token、唯讀、不含任何下單能力；首頁總資產／今日損益卡改吃真數字。紙上下單走隧道屬 Phase 3，等總司令另行核准。
>
> 六、小修：週末標頭顯示「休市」而非「已收盤(9/5)」；盤前 AI 日報功能未上線前移除其推播開關。
>
> 七、登記 P1（先不做，寫進 BACKLOG 附估時）：美股即時篩選（yfinance + IBKR 掃描器 API，誠實標回測資料品質）；ADR 溢價；法說會列表＋MOPS 簡報 PDF 連結（Phase 2 一併）；群益下單 adapter（等總司令確認資金所在）。
>
> 每項 Playwright 截圖 + smoke test，一的回補結果與二的修改前後評分對照必須附上。

- [ ] **週六.一** 千元股管線消失（證據驗證→修解析→回補price_history→影響評估→兩條閘門）
- [~] **週六.二** 評分引擎——**做法已被上方新裁示取代**：「完整度<60%不評分」取消，改為補齊八因子（見「新一」）。本項已完成的部分：**產業補齊（二.4）已完成**（`research/backfill_company_industry.py`，覆蓋率 80.8%→97.1%，台積電等電子股全部補上）；極端走勢防呆（二.3）沿用到新一.7。
- [ ] **週六.三** 三大法人柱狀圖改零基線正負向＋閘門
- [ ] **週六.四** 融資維持率分母改TWSE MI_MARGN，拔掉最後一個FinMind依賴
- [ ] **週六.五** live server新增/live/positions與/live/balance（唯讀、驗token），首頁總資產卡吃真數字
- [ ] **週六.六** 小修：週末標頭「休市」、移除未上線的AI日報推播開關
- [ ] **週六.七** 登記P1進BACKLOG附估時（美股即時篩選／ADR溢價／法說會+MOPS PDF／群益adapter）

---

## P0緊急：首頁兩個回歸（2026-09-04 13:54總司令手機實測，使用者原話全文，插最前面；修好前
暫停「首頁重排版」批次其餘項目）

原始指令全文：

> 全程繁體中文。P0 緊急：總司令手機 13:54 實測首頁出現兩個明顯回歸，插 PENDING_QUEUE 最前面，修好前暫停「首頁重排版」批次其餘項目。
>
> 一、自選股重複兩次（競態）：hydrateHome() 加防重入——用進行中旗標或版本號，新呼叫進來時取消/忽略舊的；渲染改成先在 DocumentFragment 組好五列、最後一次 replaceChildren，不要「先清空再慢慢 append」。四個呼叫點（輪詢、SSE、重新整理、切分頁）全部走同一保護。
>
> 二、走勢線壓到數字：spark() 的 SVG 明確給 width="64" height="26"（或 CSS .spark{width:64px;height:26px;flex:0 0 64px}），並把「20日／今日」標籤的包裝容器也設固定寬 64px、flex:0 0 64px；自選股列與大盤速覽列改成固定欄位版面（名稱欄 1fr、走勢欄 64px、價格欄 auto），走勢欄任何情況不得超出。每列高度一致，有線沒線都一樣高（沒線就留空位）。
>
> 三、收盤後標籤：13:30 後不得出現「盤中」；依 session 顯示「今日收盤」或「已收盤」。
>
> 四、把版面缺陷變成測試會抓的東西（smoke test 新增）：
>   check 27：自選股每個代號在 #wl-list 只能出現一次，大盤速覽每個指數只能出現一次。
>   check 28：用 getBoundingClientRect 檢查每列的走勢 SVG 與價格/漲跌元素矩形不得相交；SVG 實際寬度必須 ≤ 72px。
>   check 29：同一清單內列高差異不得超過 8px。
>   check 30：收盤時段任何列不得含「盤中」字樣。
>   以上任一失敗即 FAIL、禁止 commit。並在 Playwright 393×852 跑兩次 hydrateHome 併發呼叫，確認不重複。
>
> 五、修完附首頁截圖（自選股區、大盤速覽區）給總司令肉眼驗，smoke 30 項全綠才算完成。

- [x] **回歸.一** hydrateHome防重入——版本號`HYDRATE_HOME_SEQ`＋每個await後檢查＋DocumentFragment一次`replaceChildren`；四個呼叫點（15秒輪詢/SSE重繪/重新整理/切分頁）都呼叫同一個hydrateHome，自然共用保護
- [x] **回歸.二** spark() SVG加`width="64" height="26"`＋CSS `.spark{width:64px;height:26px;flex:0 0 64px}`、`.sparkwrap`固定64×38；`.swipe-row`/`.idx-row`改grid `minmax(0,1fr) 64px auto`；沒線也放同寬空位，實測五列列高皆63px、SVG皆64px
- [x] **回歸.三** `intradayTag(iq,us)`Actions分支依該市場session：收盤後改「已收盤 · Actions 最後一筆 約N分前」
- [x] **回歸.四** smoke新增31（併發兩次hydrateHome後代號/膠囊唯一）、32（SVG與價格矩形不相交且寬≤72px）、33（列高差≤8px）、34（收盤時段無「盤中」）——對應原話27~30；**32項全PASS**
- [x] **回歸.五** 截圖regress_wl_card.png／regress_idx_card.png／home_after_redesign.png（本機FinMind被擋所以名稱欄顯示代號，已加company_info.json退路；手機端FinMind可用會顯示中文名）

---

## 手機實測四修（2026-09-04 09:43盤中，總司令裁示「插PENDING_QUEUE最前面依序修」，
使用者原話全文；收到時零.2 tick-push補丁已寫好未套用，依規則先把零.2做完驗證commit，
接著依序修這四項，之後才回到「一／二」研究賽道轉向）

原始指令全文：

> 全程繁體中文。總司令手機實測（2026-09-04 09:43 盤中）發現四個問題，插 PENDING_QUEUE 最前面依序修，每項 Playwright 截圖 + smoke test：
>
> 一、期貨即時源回歸（先修，最小）：quotes_sinopac.json 現在只剩 5 檔＋TAIEX，TXF/MXF/EXF/FXF 近月在 tick 串流改寫時被弄丟。把期貨訂閱加回常駐行程，live server 一併提供，首頁台指期近月改走即時並標「Shioaji 即時」。
>
> 二、櫃買指數＋類股表現接即時：用 Shioaji 的指數合約群（Indexs.OTC 的櫃買指數、Indexs.TSE 的各類股指數——先列出實際可訂閱的合約代碼確認）加進常駐訂閱，live server 新增端點供市場頁讀取；連得上即時就用即時並標「Shioaji 即時」，連不上退回 market_tw.json 並明標「昨日收盤（MM-DD）」——絕不能再讓昨天的漲跌幅在今天盤中不標日期地顯示。若 Shioaji 沒有某些類股指數，誠實回報缺哪些、維持盤後並標日期。
>
> 三、走勢線改為即時 intraday sparkline：自選股每列、大盤速覽每列，連上即時時改用 /live/kbars 的當日 1 分 K 畫「今日走勢」（會隨盤中變動），離線才退回 20 日日線並標「20日」。另外修 Actions 的 fetch_sparkline_20d：2330/2454 靜默回 None 沒記錯誤，違反「禁止靜默記 None」——查出原因（疑似前兩檔先打到就被限流）、加 error 欄位、加重試。
>
> 四、健康檢查與文案對齊即時源：index.html 2209 行的「自選股台股報價 資料過舊」判斷要納入即時源——LIVE 連線且熱檔新鮮就不算過舊；「約每15秒自動更新（近即時輪詢）」那行在 SSE 連線時改顯示即時模式文案。同一頁不得同時出現「資料過舊」與「即時連線中」。
>
> 回報：四項各自截圖、smoke test、以及 Shioaji 實際可訂閱的指數/類股合約清單。

- [x] **四修.一** 期貨即時源回歸——**已完成**（commit `a8502f2`）：根因是B34改tick串流時
  `code_to_key`用`TXFR1`連續月別名當key，但tick.code是`TXFI6`實際月份碼→期貨tick全部
  反查不到被靜默丟掉（訂閱本身一直成功）。新增`_resolve_fop_key()`前三碼對回；重啟後
  /live/quotes含TXF/MXF/EXF/FXF_NEAR，Playwright實測首頁「台指期近月 Shioaji 即時 · 近月
  合約 46,164」、期貨頁四檔皆「Shioaji 即時」（截圖fix1_home_futures_live.png／
  fix1_market_fut_live.png）。順帶修掉smoke check 19在美股盤後時段的既有誠實標示bug
  （Yahoo備援收盤後被標成IBKR）。
- [x] **四修.二** ——**已完成**：Shioaji可訂閱指數合約由本機合約快取`~/.shioaji/contracts-v2-1.7/TW-IND-info.parquet`列出（226檔，其中IX*可訂閱Quote 128檔；對照表`research/data/shioaji_index_contracts.json`），**37個TWSE類股一對一全部命中**（IX0010–IX0042、IX0185–IX0188）、櫃買指數=OTC IX0043，**沒有缺漏**。常駐行程新增`INDEX_SUBSCRIPTIONS`38檔（重啟後log「INDICES x38」全部訂閱成功）；live server新增`/live/indices`（token必檢，這些指數不進stream快照）；市場頁櫃買列＋類股熱力圖連上即時標「Shioaji 即時」、離線退回market_tw.json並一律標「今日/昨日/前次收盤（MM-DD）」。smoke新增check 27（25項PASS）；Playwright：離線截圖fix2_market_offline_dated.png（「TPEx 昨日收盤（09-03）」）、即時截圖fix2_market_live_indices.png（假UDP指數推送：櫃買398.1、37/37類股）。**真實指數quote要等下一個交易日09:00後才會進來**（本次重啟已在13:35收盤後）。
- [x] **四修.三** ——**已完成**：自選股每列、大盤速覽（加權/台指期近月）連上即時時改用`/live/kbars`當日1分K畫「今日」走勢線（串流`kbars_last`逐筆併入、60秒重抓一次全量），離線退回20日日線並固定標「20日」；smoke新增check 28（26項PASS）；Playwright端到端（假1分K）：自選股2330/2454與加權/台指期皆「今日」30點（fix3_home_today_sparkline.png）。順帶修掉live server把TAIEX/TXF_NEAR誤判成美股回501的bug。**fetch_sparkline_20d靜默None根因**：2026-09-03加的240秒時間預算依字母序逐檔抓，約第60檔用完，2330之後全沒抓、也沒寫任何欄位——修法：預設自選股永遠最先抓；每檔失敗/未嘗試原因寫`quotes[code].sparkline_error`（kind:detail）、meta.sparkline記統計與停止原因；428/429先等5秒重試一次再觸發斷路器。本機實跑驗證見下一則commit。
- [x] **四修.四** ——**已完成**：`diagQuoteProblems()`抽成純函式，台股報價「資料過舊」只在Shioaji即時源也不新鮮時才報（美股同理看IBKR）；`pollStatusText()`在SSE連線中改「● 即時串流連線中（逐筆推送 tick-push），數字隨 tick 更新，已停用15秒輪詢」；連線狀態一變就重算橫幅與文案；期貨頁與首頁大盤速覽的「資料時間」跟著實際來源（即時寫即時時間，盤後明標收盤日），不再出現「四檔Shioaji即時」旁邊掛「資料時間07:24 GitHub Actions」。smoke新增check 29（27項PASS）。

---

## P0產品項目（2026-09-04上午，總司令核准，使用者原話全文；裁示「接在即時源四項修復之後
依序做」，故排在「手機實測四修」之後、「零／一／二」研究賽道轉向之前；設計依據見Cowork
文件「Alpha_產品缺口與路線圖」第一節）

原始指令全文：

> 全程繁體中文。以下為總司令核准的 P0 產品項目，append PENDING_QUEUE，接在即時源四項修復之後依序做，每項 Playwright 截圖 + smoke test。設計依據見 Cowork 文件「Alpha_產品缺口與路線圖」第一節。
>
> 一、首頁重排版（內容優先）：
> 1. 自選股區塊移到首頁最上方；每列只留名稱/代號、現價、漲跌%、今日走勢線；來源與新鮮度改為一顆彩色小點（綠=即時、黃=延遲、灰=盤後），點擊展開才顯示文字說明。
> 2. 所有系統狀態（台股/美股狀態、最後更新、即時連線、輪詢文案、匯率）合併成一條可展開的細狀態列；黃色警告只在真有問題時出現，且不得與「即時連線中」同頁矛盾。
> 3. 總資產/今日損益在未串接券商前收成一行 CTA「串接券商帳戶 →」；AI 盤前日報無內容時整張不顯示；今日事件只在有事件時顯示。
> 4. 大盤速覽改為橫向捲動的指數膠囊帶（名稱、點數、%、迷你走勢），一屏約三顆。
> 5. 底部導覽不動。
>
> 二、選股理由（個股頁總覽分頁 + 選股榜每列可展開）：
> 用 scores.json 既有六因子做「因子貢獻」橫條圖（哪幾個拉高/拉低）、原始值、全市場百分位、同產業比較；規則式一句話摘要（例：「毛利率 78 百分位、動能 91 百分位，但估值偏貴」）。保留「本榜為資料排序，未經回測驗證」標示。零外部資料。
>
> 三、個股頁新增「事件」「技術型態」兩個分頁的框架：
> 事件分頁先接已有資料（除權息事件、財報日、月營收公布日），空狀態文案統一「尚未 X ｜ 原因 ｜ 下一步」一行；技術型態分頁先放 MA/成交量指標開關（lightweight-charts 疊加），型態辨識留 P2，並在分頁頂端固定標「描述性，非預測」。
>
> 四、全站一致性：載入改骨架屏；每頁資料日期只在一處統一顯示；空狀態文案統一格式。
>
> 做完回報：首頁前後對比截圖、smoke test、選股理由範例截圖。

- [x] **P0產品.一** 首頁重排版——**已完成**（含P0緊急回歸修正後）：自選股置頂、每列名稱/代號＋現價＋%＋走勢線、來源改彩色小點（綠即時/黃延遲/灰盤後，點小點展開文字）；系統狀態（最後更新/即時連線/輪詢文案/匯率＋幣別）合併成可展開細狀態列（摘要一行＋小點）；總資產/損益收成「串接券商帳戶 →」CTA；AI日報無內容整張隱藏；今日事件只在有事件時顯示；大盤速覽改橫向膠囊帶（一屏約三顆）；底部導覽不動。smoke check 30＋31~34。前後對比：home_before_redesign.png／home_after_redesign.png
- [ ] **P0產品.二** 選股理由（六因子貢獻橫條圖＋百分位＋同產業比較＋規則式一句話摘要；
  個股頁總覽＋選股榜每列可展開；零外部資料）
- [ ] **P0產品.三** 個股頁「事件」「技術型態」分頁框架（事件接除權息/財報日/月營收公布日；
  技術型態MA/成交量開關疊加lightweight-charts，頂端固定「描述性，非預測」）
- [ ] **P0產品.四** 全站一致性（骨架屏、每頁資料日期單一處、空狀態文案統一格式）

---

## 零／一／二（2026-09-04上午，總司令裁示，使用者原話全文，依序執行）

原始指令全文：

> 全程繁體中文。以下為總司令裁示，append PENDING_QUEUE 依序執行。
>
> 零、收尾：乙.6 手機實測通過（2026-09-04 09:38，App 顯示「即時連線中 · poll-diff-2s」），PENDING_QUEUE/BACKLOG 劃掉。下一個 App 項目：把 /live/stream 從「2 秒輪詢比對」改成「shioaji_quotes.py 收到 tick 回呼就直接推給 SSE」的真逐筆推送，改完 mode 標籤改為 tick-push；沿用既有 token/共用記憶體模式，不開第二條 Shioaji 連線。
>
> 一、研究賽道轉向（總司令裁示）：從「橫截面選股」轉為「regime 擇時／下檔保護 overlay」
> 背景：#1–#27 橫截面因子與複合全 FAIL，且 300 檔校準證明管線正常（B31）。在免費資料宇宙裡「買哪幾檔」無 edge，停止再丟裸因子。改打「什麼時候該降曝險」，這直接服務「永遠不要賠錢」第一原則。
>
> 1. 基底固定為最簡單的被動部位：TAIEX（或 0050）買進持有；美股軌用 SPY。overlay 若連被動指數都保護不了，就保護不了任何東西。
> 2. 評估指標全面改為下檔導向：MDD、下檔捕捉率（downside capture）、地雷率、Sortino、Calmar、最差 12 個月。過關門檻（TRAIN 先訂死、不准看結果回調）：MDD 較基底降 ≥35%，且上檔捕捉率 ≥75%，且在 6 個歷史危機視窗（2008/2011/2015/2018/2020/2022 各自）中 ≥5 個回撤有縮小。alpha 顯著性不再是門檻，只回報。
> 3. 候選訊號（每個參數 ≤2 個，抗過擬合）：#28 市場廣度（% 站上 200MA、A/D line、新高新低差）；指數 200MA 趨勢濾網；已實現波動 regime（20 日 vol 分位）；融資餘額成長率當「風險」訊號重測（#26 曾到 88.5 百分位，改用下檔指標評估）；由高點回撤 X% 的斷路器。每個先寫經濟理由：為什麼這個訊號在危機前會先動。
> 4. 專屬控制組（比橫截面更嚴）：(a) 隨機開關對照——用相同「在市時間比例」隨機切換 ≥300 次，overlay 的 MDD 改善必須 >90 百分位；(b) 訊號延遲 1 週再測——若延遲後失效，代表有前視偏誤，判死；(c) 全額計入來回成本與 whipsaw 次數；(d) 參數高原；(e) OOS 期危機視窗必須同樣縮小回撤。
> 5. 快殺紀律：TRAIN 期 6 個危機視窗若 <4 個縮小回撤，直接判死進墓園，不進深度驗證。
> 6. 有任何一個 overlay 通過完整關卡、要進 forward-paper 前停下提案給總司令；死路記墓園續跑。
>
> 二、FUT 軌配合：跨商品日報酬池（第335輪已建）改為測試同一套 regime overlay 對期貨曝險的下檔保護，不再做期貨單因子。
>
> 做完回報：乙.6 劃掉、tick-push 進度、regime 賽道第一個訊號的 TRAIN 危機視窗結果。

- [x] **零.1** 乙.6劃掉（PENDING_QUEUE/BACKLOG）——已完成
- [x] **零.2** `/live/stream`改真逐筆推送（tick回呼→SSE），mode改`tick-push`——**已完成**
  （commit `a8502f2`）：shioaji_quotes.py每筆tick經loopback UDP（127.0.0.1:8002，帶同一份
  token）推給alpha_live_server.py，伺服器LiveMem＋asyncio.Condition喚醒SSE，事件
  mode=tick-push（250ms合併）；沒新鮮tick自動退回poll-diff-2s。端到端：push→SSE 257ms、
  錯token被拒；正式上線後/health `stream_mode=tick-push`、30秒1522筆tick；手機端狀態列
  已顯示「逐筆推送・tick-push」。
- [ ] **一** 研究賽道轉向regime擇時／下檔保護overlay：寫進協定＋規格書
  （門檻TRAIN先訂死）＋第一個訊號TRAIN危機視窗結果
- [ ] **二** FUT軌改測同一套regime overlay對期貨曝險的下檔保護

---

## 乙.4/乙.5補充（2026-09-03深夜，執行P0三-三收尾時收到，使用者原話全文，
依插隊保護規則先登記；使用者明講「繼續做乙.4跟乙.5」，故P0三收尾後直接接
乙.4/乙.5＋這三個修正，甲/乙.1等其餘項目維持在佇列，之後依序做）

原始指令全文：

> 全程繁體中文。收到，繼續做乙.4（前端偵測隧道）跟乙.5（TradingView圖表），並補三個修正：
>
> 一、/live/kbars 501 的正確修法：不要開第二條 Shioaji/IBKR 連線（你的顧慮是對的，會跟現有常駐連線衝突）。改成在 shioaji_quotes.py 那支常駐行程裡——它本來就持續收到 tick——額外維護一份「當日每分鐘 OHLC」的記憶體聚合（用已收到的 tick 自己算，不用另開連線、不用額外 API 呼叫），alpha_live_server.py 的 /live/kbars 直接讀這份共用記憶體，跟 /live/quotes 現在的做法一致。美股 IBKR 那端如果要 kbars，同樣道理先確認會不會衝突，不確定就先回報、不要硬做。
>
> 二、/live/stream 誠實標示：目前是「每2秒輪詢比對再送」不是真逐筆推送，這個判斷正確、先不用急著改。但要讓它在回應/文件裡明確標出來（例如加一個 mode:"poll-diff-2s" 欄位或注解），不要讓之後接手的人誤以為是真推送。之後排進佇列（不用現在做）：把它改成真正由 tick 回呼觸發推送（shioaji_quotes.py 收到一筆 tick 就直接餵給 SSE，不是輪詢），這才是真正的秒級。
>
> 三、安全加固：即使流量已經過 Private Network + WARP 裝置驗證，三個端點仍然一律要求既有的 X-Alpha-Local-Token 驗證，不要因為走了私有網路就跳過——多一層防護不嫌多，這支伺服器雖然無下單能力，但風險評估以最嚴標準做。
>
> 做完乙.4/乙.5 後回報，附上：三個端點目前的驗證/聚合狀態、smoke test 結果。

- [x] **補一** ——**已完成**（commit `49a0ead`）：`shioaji_quotes.py`的
  `TickState.add_tick()`用已收到的tick聚合當日每分鐘OHLCV（不另開連線、
  不呼叫api.kbars()），`maybe_write_live_state()`每秒最多一次把「最新快照
  +當日1分K」原子寫進本機熱檔`research/.live_state_sinopac.json`
  （gitignored）；`alpha_live_server.py`三端點優先讀熱檔（120秒內新鮮）、
  否則退回git冷檔，`/live/kbars`回`mode:"tick-aggregated-1m"`。「共用記憶體」
  的誠實說明：兩個獨立行程在Windows上共用資料，用同機本地熱檔是最不需要
  額外相依的做法，跟`/live/quotes`原本讀JSON檔的做法一致；真正同一行程
  共用物件要等兩支合併（見BACKLOG登記待辦5）。**美股IBKR 1分K未做，回501**：
  `ibkr_quotes.py`是短命輪詢腳本、沒有常駐tick可聚合，要做得先確認
  `reqHistoricalData()`會不會跟現有連線衝突，照使用者裁示不硬做、先回報。
- [x] **補二** ——**已完成**：每個SSE事件payload帶`mode:"poll-diff-2s"`、
  `/health`回`stream_mode`，docstring/端點docstring都明寫「輪詢比對不是真
  推送」；「tick回呼直接推SSE」已登記BACKLOG登記待辦第5條，未動工。
- [x] **補三** ——**已完成**：三個/live端點程式碼裡只有一條`_check_token()`
  路徑、沒有任何「私有網段免token」分支，docstring明文禁止之後加；
  `/health`回`token_required_on_live_endpoints:true`。本機實測無token一律401。
- [x] **乙.4** ——**已完成**：設定頁「即時伺服器」卡片（網址/token存本機
  localStorage、測試連線）；App用`fetch()`讀SSE（原生EventSource不能帶token
  標頭，刻意為了保住補三的驗證）、指數退避重連、切回前景重連；連線中
  `fastPollTick`停用、Actions冷檔60秒內不重抓；首頁與設定頁狀態列：連上
  「● 即時連線中（本機伺服器・熱檔秒級・poll-diff-2s）」，連不上/未設定
  「離線（…），顯示最後收盤 MM-DD」。
- [x] **乙.5** ——**已完成，一處偏差要回報**：個股頁走勢改TradingView
  lightweight-charts 5.2.1（Apache-2.0）。**cdnjs沒有收錄這個函式庫**
  （api.cdnjs.com搜尋為空），改用官方npm經jsdelivr發行、版本釘死，
  async載入、載不到自動退回既有SVG折線。日線沿用既有FinMind資料；連上
  即時伺服器且該檔有1分K時自動切「1分K(即時)」、可手動切回日線；串流
  每個事件帶`kbars_last`→`series.update()`逐筆更新，不必另外打/live/kbars。
- [x] **乙.6**（**2026-09-04 09:38總司令手機實測通過：App顯示「即時連線中 · poll-diff-2s」**）——Playwright+smoke test部分已完成（smoke 23項全PASS含
  新增25；端到端：假熱檔+本機伺服器→串流連上→首頁價格跳動→個股頁1分K
  17根隨事件更新→拔掉伺服器退回離線標示，GLOBAL_ERRORS=[]）；**「下次台股
  開盤總司令手機開App看台積電數字與K線每秒在動」這半段要等**：(1)乙.3
  cloudflared `service install`需總司令用系統管理員視窗執行＋Cloudflare
  Access設定；(2)`alpha_live_server.py`要在本機常駐啟動（目前只有手動
  `python research/alpha_live_server.py`，尚未掛排程）；(3)真實tick進熱檔
  要等開盤（tick.datetime欄位聚合邏輯只用假tick驗過）。

---

## 甲乙丙（2026-09-03，總司令裁示，接在P0三之後依序執行——**部分內容
會取代/推進P0三-四/五、也會取代下方稍早的「校準探針」條目，這是目前
最新、範圍最大的一批指示**）

原始指令全文：

> 全程繁體中文。以下為總司令裁示，append PENDING_QUEUE，接在正在做的 P0 修復之後依序執行。
>
> 甲、三軌馬拉松解除暫停（總司令裁示：確認 SPEC＋解除暫停）
> 1. research/PORTFOLIO_STRATEGY_SPEC.md 第 3 行狀態改為「已確認（2026-09-03 總司令）」，規則內容不動、不得因回測結果回頭偷改。
> 2. MARATHON_PROTOCOL.md 第 0 節暫停規則解除，三軌恢復實質工作，主軸改為多因子組合策略（portfolio_multifactor v2 及其迭代），不再單因子亂挖。
> 3. 但恢復前先跑「管線校準探針」（上次指令未被登記，這次務必登記執行）：拿橫截面 12-1 動能當已知應有訊號的 benchmark 過同一套 cheap gate + gauntlet。結論(甲)管線正常→v2 的 p=0.053 視為真的差一點，照 SPEC 繼續迭代；結論(乙)檢定力不足（樣本 N 太小、null 分布不合理）→先修管線再跑，並回頭把先前 N<30 的 FAIL 標「未定」。校準結論回報總司令。
> 4. 通過完整 gauntlet、要進 forward-paper 前才停下提案；死路記墓園續跑。
>
> 乙、Phase 1 即時架構「冷熱分離」（總司令核准動工；架構細節見 Cowork 提案文件，照此實作）
> 1. 停止盤中 git push：research/shioaji_quotes.py 盤中只更新記憶體，不 commit；13:30 收盤後寫一次當日收盤快照 commit（一天 1 次）。美股 ibkr_quotes.py 同理（收盤後一次）。驗收：當日 repo commit 數 < 20，Actions 報價/大盤排程當日落地次數恢復正常。
> 2. 新增本機 alpha_live_server.py（FastAPI，沿用 ibkr_order_server.py 的 token/白名單模式）：GET /live/quotes（快照）、GET /live/stream（SSE 逐筆）、GET /live/kbars?code=（當日 1 分 K，Shioaji api.kbars()；美股用 IBKR reqHistoricalData）。只聽本機 port，只開讀取端點，不開任何下單端點。
> 3. cloudflared 建 Tunnel 對外，前面設 Cloudflare Access（免費）email OTP 保護；隧道 token 與設定放本機 secrets/（.gitignore 已擋）。寫一份使用者操作步驟（申請 Cloudflare 帳號→建 Tunnel→設 Access）給總司令自己操作，任何需要登入/填資料的步驟由總司令親自做。
> 4. App 前端：偵測隧道可用→改用 SSE 即時更新數字與 K 線；連不上→退回 git 冷資料並明確標「離線，顯示最後收盤 MM-DD」。標籤規則沿用：即時(tick)／今日收盤／日線 T-1。
> 5. 個股頁改用 TradingView lightweight-charts（Apache-2.0，cdnjs 載入、版本釘死）：盤中 1 分 K 來自 /live/kbars，逐筆 series.update()；歷史日線沿用既有資料。
> 6. 驗收：Playwright + smoke test；並在下次台股開盤，總司令手機開 App 看台積電數字與 K 線每秒在動。
>
> 丙、之後分期（登記進 BACKLOG，先不做）：Phase 2 新聞管線（MOPS/EDGAR/RSS 標題連結＋割韭菜過濾）＋籌碼集中度模組（集保 TDCC OpenAPI 大戶週變化＋TWSE OpenAPI 外資/借券/當沖）；Phase 3 paper 下單走隧道（Access 保護），真實下單永遠只在本機且使用者親按。
>
> 全部做完回報，附 commit 數、Actions 落地次數、smoke test 結果、Cloudflare 操作步驟文件。

- [x] **甲.1** `PORTFOLIO_STRATEGY_SPEC.md`第3行狀態改「已確認
  （2026-09-03總司令）」，規則內容不動——**已完成**（commit `8aad0d4`）
- [x] **甲.2** `MARATHON_PROTOCOL.md`第0節暫停規則解除，主軸改多因子
  組合策略（portfolio_multifactor v2迭代），不再單因子亂挖——**已完成**
  （commit `8aad0d4`：🛑區塊整段換成「✅暫停規則解除」，明訂每輪工作單位必須是
  組合策略層級推進，單因子IC只允許作為組合成分替換候選的前置檢查；並要求
  馬拉松開工先讀`CALIBRATION_PROBE.md`的校準結論）
- [x] **甲.3**（**已完成，結論(乙)檢定力不足——樣本太小；已修管線SAMPLE_SIZE 100→300、#77/#79/#91/#47/#52/#34標未定，完整見`research/CALIBRATION_PROBE.md`**）管線校準探針（正式登記執行）：12-1動能benchmark過同一套
  cheap gate+gauntlet，判定管線正常(甲)還是檢定力不足(乙)，回報結論；
  若(乙)要回頭把先前N<30的FAIL標「未定」——**執行中**：
  `research/calibration_probe_momentum_12_1.py`（新增）四段：A標準100檔cheap
  gate／B檢定力診斷（null sd、80%檢定力最小可偵測IC）／C 300檔大樣本＋20組
  100檔子樣本漏殺率／D組合層gauntlet縮影（v2引擎、等權、季/月頻、隨機對照30次、
  成本1x/2x/3x）。結論寫`research/CALIBRATION_PROBE.md`。
- [x] **甲.4** 解除暫停後：通過完整gauntlet要進forward-paper前才停下
  提案，死路記墓園續跑（沿用既有紀律，不必額外改檔案）——**已在
  `MARATHON_PROTOCOL.md`第0節新版第4點重申，無其他改動**
- [x] **乙.1** Phase 1冷熱分離：shioaji_quotes.py/ibkr_quotes.py盤中只
  更新記憶體不commit，收盤後一天commit一次——**已完成**（commit `6ad70f5`）：
  `shioaji_quotes.py`新增`INTRADAY_GIT_PUSH=False`，盤中`_flush_and_push()`
  直接return（不寫冷檔、不碰git，只寫熱檔給live server），收盤收尾
  `final=True`寫冷檔並commit+push一次；回歸測試11項PASS。IBKR那端：
  **查明`ibkr_quotes.py`根本沒有掛任何Windows排程任務**（只有AlphaData/
  AlphaHypothesisQueue/AlphaMarathon/AlphaShioajiQuotes四個，這就是
  quotes_ibkr.json停在09-02 23:25的原因——之前是手動跑的），`C:lpha\n  run-ibkr-quotes-cycle.ps1`（repo外）已改成美東正常盤盤中不commit、盤後
  才commit一次；要不要建AlphaIbkrQuotes排程（需IB Gateway常開）留給總司令決定。
  **驗收「當日commit<20」要等下一個交易日觀察。**
- [x] **乙.2** 新增`research/alpha_live_server.py`——**已完成第一版，
  誠實範圍見檔案docstring**：`/live/quotes`已完整可用（讀既有JSON
  快照）；`/live/stream`目前是輪詢重新比對再送（非真逐筆tick，因為
  `shioaji_quotes.py`的`TickState`只存在它自己行程記憶體，這支獨立
  伺服器讀不到，要做到真逐筆需要下一輪把兩個行程合併/共用記憶體）；
  `/live/kbars`回501尚未實作（避免另開一個Shioaji連線跟現有常駐行程
  衝突）。監聽`0.0.0.0:8001`（不是127.0.0.1，理由：Cloudflare Tunnel
  Private Network路由連的是區網IP不是loopback），靠token擋未授權
  存取。實測`/health`/`/live/quotes`(401/200)/`/live/stream`(SSE事件
  正確送出)/`/live/kbars`(501)/LAN IP連通皆通過。commit `4fb191a`已push。
- [x] **乙.3-前置** cloudflared本體已透過`winget install Cloudflare.
  cloudflared`裝好（`C:\Program Files (x86)\cloudflared\cloudflared.exe`
  version 2026.8.3）。**`service install <token>`這條指令本身無法由我
  執行**——實測回傳「Cannot establish a connection to the service
  control manager: Access is denied」，這是Windows Service Control
  Manager要求的Administrator權限，我這邊的終端機工具沒有、也無法自我
  提升到系統管理員層級（沒有互動式UAC同意窗可以按）。**需要總司令自己
  開一個「以系統管理員身分執行」的PowerShell/CMD視窗，貼上同一條指令
  跑一次**（`cloudflared.exe`已經裝好，這步只差權限，不是任何設定
  錯誤）。已用`ipconfig`/`Get-NetIPAddress`查到區網IP：**Wi-Fi介面
  192.168.3.241**，供設定Private Network路由CIDR用。
- [x] **乙.4** App前端偵測隧道可用性，SSE即時更新/離線退回冷資料標示——**已完成，見上方「乙.4/乙.5補充」區塊**
- [x] **乙.5** 個股頁改用TradingView lightweight-charts（cdnjs未收錄→jsdelivr釘死5.2.1），盤中1分K走/live/kbars——**已完成，見上方「乙.4/乙.5補充」區塊**
- [x] **乙.6** 驗收：Playwright+smoke test已完成；cloudflared服務／防火牆／`AlphaLiveServer`常駐皆就緒；**總司令手機實測2026-09-04 09:38通過**（「即時連線中 · poll-diff-2s」）
- [x] **丙** Phase 2（新聞管線+籌碼集中度模組）+ Phase 3（paper下單走
  隧道）——**已登記進BACKLOG.md「登記待辦」區塊，未開工**

---

## （已併入上方「甲乙丙」區塊的甲.3/甲.4——這是同一件事第一次被提出時
的原始記錄，保留供追溯，執行以上方甲乙丙區塊為準，不要重複做）

原始指令全文：

> 全程繁體中文。append 到 PENDING_QUEUE，不打斷當前馬拉松，依序執行。
>
> 背景：佇列 #1–26 全 FAIL、0 個活到組合層；連跨 19 國最穩健的毛利率(GP)在我們管線也是噪音(實作已證無 bug)。兩種可能必須先分辨：(甲)這些軸真的沒 edge；(乙)cheap gate 樣本太小、檢定力不足而錯殺（#20 N僅47–74、#25僅N=3–4，這種樣本的 FAIL 沒有統計意義）。
>
> 一、管線校準探針（最優先，先做）：
> 拿「全球最穩健的橫截面股票動能：過去12個月報酬、跳過最近1個月（12-1 momentum）」當作已知應該有訊號的 benchmark，用我們現有 cheap gate + 完整 gauntlet 同一套流程跑一次。目的不是找策略，是校準管線：
> - 若連 12-1 動能都顯示噪音／過不了 cheap gate → 是管線檢定力/樣本問題（乙）：檢查每期橫截面樣本數 N 是否過小、null 分布建構是否合理、IC 統計頻率是否用對。修好前，先前所有「FAIL」判定都要打問號、不得再據此判死。
> - 若 12-1 動能清楚有訊號、正常通關 → 管線沒問題（甲）：接受「這些軸沒肉」，回報並停下，讓總司令決定要不要換完全不同的方法（事件驅動、另類資料、更高頻），不要再對同類橫截面因子硬挖。
> 把校準結論（甲或乙）回報總司令。
>
> 二、#27 多因子 z-score 複合評分：照原設計跑。但若結論是（乙），先修管線再跑 #27，否則結果一樣不可信。
>
> 做完回報，等總司令看校準結論再定方向。

---

## 佇列（2026-09-03，使用者裁示，不打斷正在跑的馬拉松，排在當前假說之後執行一次）

原始指令全文：

> 全程繁體中文。append 到 PENDING_QUEUE，不打斷正在跑的馬拉松，排在當前假說之後執行一次即可。
>
> 針對已判 FAIL 的 #20（純毛利率 Gross Profitability）做一次「實作正確性健檢」再認死。理由：GP 是跨 19 國+新興市場實證最穩健的品質因子之一，死在「mean_ic ≈ noise」與強證據矛盾，疑似實作/資料問題而非真的無訊號。只查以下四點，不要重跑全套 gauntlet：
> 1. 公式：GP =（營業收入 − 營業成本）/ 資產總額，確認分子分母對應台股財報科目正確、沒拿錯欄位。
> 2. Point-in-time：財報發布日對齊，確認沒用未來資料、也沒因發布延遲讓訊號整體 lag 一季。
> 3. 涵蓋率：算出 GP 有值的股票比例，若大量 NaN 被當 0 或被剔除會把 IC 稀釋成 noise。
> 4. 方向：確認是「高 GP 做多」沒接反。
> 回報：若四點都正確、IC 仍是 noise，就正式接受 FAIL 留墓園；若發現 bug，修正後只重跑 gate1 看是否復活，復活才排回完整 gauntlet。
> 其餘 #21–#24 的 FAIL 維持判死，不複查。做完繼續原本馬拉松佇列。

- [x] **#20 GP實作正確性健檢**——**已完成**：四點皆查證正確（公式數值
  上精確驗證diff=0.0、PIT對齊共用已驗證機制、涵蓋率跟CHEAP_PASS因子
  同量級、方向兩期皆正未接反），無bug，正式接受FAIL維持墓園，未重跑
  gauntlet。見`HYPOTHESIS_QUEUE.md`#20「實作正確性健檢」章節。

---

## 佇列（2026-09-03，使用者裁示，不打斷當前馬拉松，接續#20健檢之後登記）

原始指令全文：

> 全程繁體中文。新增研究方向，append 到 HYPOTHESIS_QUEUE 與 PENDING_QUEUE，照既有紀律跑，不打斷當前馬拉松。
>
> 新方向：多因子「複合評分」策略（z-score blend，非單因子、非硬 AND 堆疊）
>
> 教訓：#22 是硬 AND 組合，死在 sanity 14%——合取把宇宙砍太小、過度擬合特定組合。改用穩健的 z-score 複合。
>
> 方法：
> 1. 選 3–5 個「經濟理由獨立、彼此低相關」的因子（例：品質=GP 或 ROE、價值=B/P 或 E/P、動能=中期、TW專屬=月營收意外 或 法人連續性）。各自算標準化 z-score。
> 2. 等權（或依既有驗證強度加權）加總成複合分數，做多 top decile、月度再平衡、全額成本。
> 3. 因子相關性要低：先算相關矩陣，高度相關的只留一個。複合價值來自分散因子特異風險，不是疊同一訊號。
>
> 抗過度擬合控制要比單因子更嚴（組合放大 p-hacking 風險）：
> - 隨機對照 draws ≥300，且對照組是「隨機選同數量因子亂加權」，證明贏的是這個特定複合、不是任意複合都贏。
> - 因子權重只准用 TRAIN 期決定並凍結，OOS 前不得回調。
> - 正交性檢查：複合超額對每個單因子回歸，確認 alpha 不是只重新表達某一個因子（否則是偽複合）。
> - 逐年 ≥5/6、成本 1x/2x/3x、leave-one-factor-out（拿掉任一因子看邊際貢獻）。
>
> 先跑 baseline 複合（GP + 價值 + 月營收意外，等權），過 cheap gate 才打完整 gauntlet；過不了就換因子組合，但每次先寫「為什麼這幾個因子互補」的經濟理由。通過完整 gauntlet、進 forward-paper 前停下提案給我。

- [x] **登記z-score複合評分假設進HYPOTHESIS_QUEUE.md**——**已完成**：
  登記為#27，排隊接續#26之後，完整方法論（隨機對照≥300draws、正交性
  檢查、TRAIN期凍結權重、leave-one-factor-out）已寫入
  `HYPOTHESIS_QUEUE.md`#27，尚未開始第1關，交由馬拉松自主接續。

---

## 佇列（2026-09-03，使用者裁示，收到時手上沒有其他進行中任務，直接依序處理）

原始指令全文：

> 全程繁體中文。以下為總司令已核准的任務，append 到 PENDING_QUEUE，做完手上的再依序執行。
>
> 一、Shioaji 報價升級為逐筆 tick 串流（B21）：
> - 把本機 Shioaji 報價程式從現在的「輪詢快照」改為「訂閱 quote callback 逐筆串流」（api.quote.subscribe + set_on_tick_stk_v1 / set_on_bidask 回呼），即時把最新成交價/量寫入本機報價狀態。
> - 開盤時段（台股 08:30–13:45）提高「生成報價 JSON + git push」的頻率——本次頻率調整總司令已核准，不需再提案；請直接實作並在 PROGRESS 回報你設定的實際頻率與理由。
> - 非開盤時段維持休眠、寫 market_closed，不空跑。
> - 產物報價 JSON 每檔標「即時(tick)」；推送沿用既有 fetch+rebase 重試與 concurrency group，避免撞車。
> - 驗證：寫一支單元測試模擬 tick 回呼→狀態更新→JSON 寫出；並在下次開盤留一段實際 tick log 佐證確實逐筆進來（開盤前先把程式備妥）。
>
> 二、把「秒級即時（手機端）」登錄為 BACKLOG 的未來必做架構項（B20），內容註明：
> - 瓶頸不在永豐 API，Shioaji 來源端已可逐筆；卡在「本機→git push→GitHub Pages CDN→手機 fetch」慢鏈路。
> - 解法：雲端中繼（本機 tick → 雲端 websocket/DB → 手機直連），繞開 GitHub Pages。
> - 屬架構變更，動工前必須先提完整提案＋金鑰/連線安全風險評估給總司令核准，現在不要開工。
>
> 做完一、驗收後，馬拉松繼續自主跑。

- [x] **一** Shioaji報價升級為逐筆tick串流（B34，原始編號B21跟既有
  「Reddit社群訊號抓取」條目撞號）——**已完成**（見`BACKLOG.md`/
  `PROGRESS.md`對應條目：改成`api.subscribe()`常駐訂閱、15秒flush+push、
  單元測試6項全PASS、smoke check 22 PASS，下次台股開盤才能做最終SDK
  行為驗證，已誠實記錄）。
- [x] **二** 登錄B35（秒級即時手機端架構項，原始編號B20跟既有「未來性
  濾網(c)類因子」條目撞號）到BACKLOG.md，只登記不開工——**已完成**
  （見`BACKLOG.md`對應條目，commit `8b65e72`）

**（2026-09-03同一指令稍後補充，使用者原話追加，收到時一還在處理中，
內容原封不動記錄，做完一之後接續）**：

> 三、做完一、驗收後，接著繼續自主挖礦馬拉松：
> - 先把目前排隊的 6 個假說依序挖完：#19（跨市場美股隔夜外溢）、#20（純毛利率 GP）、#21（月營收意外×低關注度）、#22（品質×營收加速×法人吸籌+低波動閘門）、#23（F-score 排雷閘門）、#24（除權息季節效應）。
> - 挖完這 6 個後，再自行尋找新方向（社群/論壇/GitHub/學術/實戰圈找靈感，不能全用就改造+驗證，不丟裸因子等死）。
> - 紀律：便宜關卡（sanity / 隨機對照 / gate1 IC）若給出「便宜且決定性」的負面證據，就快速判死、寫進墓園、換下一個，不要在沒肉的方向硬灌 1000 draws 或密集參數網格浪費算力與時間；只有便宜關卡已見生命跡象的方向，才投入深度驗證。反過來也不准偷懶亂殺——判死一定要有便宜且決定性的證據，不能沒驗證就草草說無效。
> - 全程照三大停下條件才停問總司令；有任何一個通過完整 gauntlet、要進 forward-paper 前才停下提案。

- [x] **三**（2026-09-04凌晨確認）馬拉松與假說佇列排程皆存活：`AlphaMarathon`最近一輪第324輪(US)、`AlphaHypothesisQueue`正在跑#27第2關300-draw隨機對照，#19~#24已全部結案（見TRIALS_LEDGER #90~#96），佇列非空（#27進行中、#5/#6/#8/#10卡外部依賴）。原條目：確認馬拉松繼續依序挖#19~#24，快殺紀律（便宜且決定性證據才
  判死，不偷懶亂殺也不硬灌算力）——**這已經是`HYPOTHESIS_QUEUE.md`
  最上面「快殺標準」既有明文規定，不是新規則，做完一之後只需確認
  馬拉松排程仍存活、佇列非空即可，不需要另外改檔案**。

---

## 佇列（2026-09-01 23:5x 使用者裁示「隔夜自主批次」，拆解自單一指令，依序處理）

**背景查證（處理前）**：`research/.hypothesis_queue.lock`目前是活的
（PID 47756），代表挖礦馬拉松（`AlphaHypothesisQueue`排程）本來就還在
自主跑，正在處理Carry #4（抓到並修好一個0筆交易的真bug，重跑中）——
不是停著要「恢復」，指令裡的前提（馬拉松已停）不成立，如實記錄。

- [x] **一.1** IBKR紙上下單測試（1股AAPL，送單前assert paper帳戶，記
  paper_trades.json）——**已於稍早完成**（見`BACKLOG.md`「2026-09-01
  （續）IBKR paper下單管線測試」條目：BUY 1股AAPL Filled@324.58→SELL
  平倉Filled@324.61，帳戶歸零），依指令「若已跑過就跳過」，跳過不重做。
- [x] **一.2** Shioaji台股紙上下單「程式建好但不送單」——**已完成**
  （見`BACKLOG.md`「2026-09-01（續）Shioaji台股paper下單伺服器」條目：
  `research/shioaji_order_server.py`建好，login+帳戶白名單驗證通過，
  完全沒有呼叫過`/submit_order`送測試單，留到開盤且使用者親按才做）。
- [x] **二.1** 掃`index.html`所有「建置中/尚未實作/尚無評分/尚未接上」
  區塊，列成清單——**已完成**（session內部完成，清單見稍早派工B29
  agent時給的完整分類：可建/卡資料源/Phase2占位三類，未另存獨立文件）。
- [x] **二.2** 有現成資料源的直接建：今日事件接earnings_calendar已完成
  （見`BACKLOG.md`「2026-09-02 App功能補完」條目）；**B29美股財報yfinance
  因子管線已完成並驗證**（`commit 8b04197`：實測6檔yfinance欄位後選定
  毛利率/營業利益率/營收年增率/FCF margin四指標，`data/us_financials.
  json`6/6檔成功、數字合理性人工複查通過，例如NVDA毛利率71%/AMZN FCF
  margin僅1%皆符合各自業務特性——**只做後端管線，`index.html`還沒有
  顯示這些指標的UI區塊，也還沒掛GitHub Actions排程**，留給下一輪）。
- [x] **二.3** 設定頁那行diag灰字讀數收進隱藏debug開關（平常不顯示）——
  **已完成**（見`BACKLOG.md`同上條目：點「App版本」5下切換，預設隱藏，
  Playwright驗證過行為正確）。
- [x] **二.4** 加smoke test防線：資料檔明明新鮮、App卻顯示無資料=FAIL
  （SW快取壞殼那類）——**已完成**（`scripts/smoke_test.mjs`新增檢查15，
  13項全PASS）。
- [x] **三.1** Carry #4判生死（alpha顯著性+下檔保護），PASS進監控台、
  FAIL進墓園——**馬拉松已自主跑完並結案：FAIL**（第八輪，alpha顯著性
  未過，TRAIN p=0.4868/VAL p=0.1487皆遠不顯著，見`HYPOTHESIS_QUEUE.md`
  排隊順序總結item 4、`STRATEGY_GRAVEYARD.md`/`TRIALS_LEDGER.md`#75）。
- [x] **三.2** B25 regime分情境報告、B26調整後Sharpe(×0.5/×0.7)+CVaR
  ——**B26確認早已隨B24-500完成**。**B25於2026-09-02完成**（範疇⚠️：
  只做價值成長板，題材動能/未來性無PIT引擎不適用；隨機對照組百分位
  誠實留白，未重新產生逐日層級的隨機序列）。關鍵發現：「空頭+非高
  波動」是表現最差的情境組合，見`research/B24_RESULTS.md`「B25分情境
  績效報告」章節、`BACKLOG.md`B25條目完整記錄。
- [x] **三.3** `HYPOTHESIS_QUEUE.md`新增7條新方向（殘差動量/regime擇時
  overlay/產業內相對強度/betting-against-beta/台股三大法人連續買超/
  台股月營收公布事件效應/波動度目標化），各自經濟理由+事前綁定關卡——
  **已完成**：等到`.hypothesis_queue.lock`釋放後，用具名鎖安全取得、
  寫入#9~#15完整內容+更新排隊順序總結，寫完立即釋放鎖（占用時間<1分鐘）。
  內容被同一時段的馬拉松cycle（Carry #4那輪）一併commit進`2b73f69`（
  跟它自己對Carry狀態的更新同一個commit，不是我自己單獨commit，但內容
  完整無缺，已用`git diff HEAD`確認落地、`grep`確認3處文字都在）。
- [x] **四** 全部做完且各自驗收後，確認挖礦馬拉松（假設佇列自動排程）
  持續運作，一條接一條不idle——**2026-09-02T21:5x再次確認**：
  `AlphaMarathon`/`AlphaHypothesisQueue`兩個Windows排程皆`Ready`狀態且
  最近一次執行成功（`LastTaskResult=0`）；`hypothesis_queue`軌過程中
  發現一次排程崩潰（PID 60976在完成#16判定後commit前中斷，跟今晚稍早
  兩次API中斷同一類問題），已接手修復（清乾淨鎖檔+補commit+修正
  `MARATHON_LOG.md`格式損壞，見對應commit），佇列非空、`#17`已排定
  接續。**同時發現一個獨立於本次任務的既有缺口**：`AlphaIbkrQuotes`
  排程從未真正建立過（`BACKLOG.md`「本機排程」條目本來就寫明卡在
  Claude Code安全分類器擋下建立排程的動作，需要使用者自己跑
  `schtasks`），`data/quotes_ibkr.json`已停留在2026-09-01 21:34沒更新
  超過24小時——不是本次改動造成的迴歸，是舊缺口一直沒補，如實記錄
  留給使用者決定要不要現在補。

**鐵律（適用於這整批）**：資料源禮儀（≥3秒/斷路器/不打爆FinMind/TWSE/
永豐）、determinism、paper-first、真實下單永遠使用者親按、金鑰/憑證不進
commit、假資料零容忍寧可空狀態、流程重於盈虧、動`index.html`→smoke全綠
才commit、每完成一項在`MARATHON_LOG.md`寫一行+這份檔案更新剩餘筆數、
全程繁體中文。

---

## 佇列（2026-09-02凌晨，隔夜批次進行中收到，使用者原話全文，排在隔夜
批次之後處理，使用者自己也明講「排在隔夜其他項之後、不影響馬拉松」）

- [~] **App 台股新增「籌碼」分頁（免費層今晚做，分點層登錄待付費決策）**——
  **2026-09-04凌晨完成第一單位（commit `130df4e`）**：個股頁籌碼分頁新增
  「三大法人逐日／累計買賣超」表（外資/投信/自營/合計/累計，讀既有
  `stock_detail.json` institutional.history，目前5個交易日、每日排程會變長）、
  「外資估算成本」（淨買超日張數×當日收盤加權概算，明標「估算、非精確成本」，
  有走勢圖時畫成priceLine）、籌碼免責文字（非投資建議／跟著大戶不等於獲利／
  大戶也可能出貨／尚未經signal_ledger校準）；融資融券變化本來就有。smoke
  check 26，24項全PASS。**未做、已登記BACKLOG提案**：股權分散/千張大戶週變化
  （FinMind `TaiwanStockHoldingSharesPer`）、借券賣出（TWSE `TWT93U`）——都要
  新的Actions抓取腳本＋market.yml步驟（PAT地雷），且這台機器對FinMind曾被封鎖
  無法本機實測，依「提案先於執行」先提案；分點層已登錄BACKLOG「卡付費資料源、
  待使用者決定」。

  **查證發現（處理前，2026-09-02凌晨）**：這個任務比字面上看起來大很多，
  誠實記錄，不要低估：
  1. **App層目前沒有「個股每日籌碼」JSON管線**——`research/twse_t86_
     client.py`（三大法人T86）是研究馬拉松用的parquet快取，服務對象是
     因子回測，不是App每天讀的JSON；`data/margin_maintenance.json`只有
     6筆「大盤整體」融資維持率，不是逐股資料。要做這個功能，第一步得先
     新增一支`.github/scripts/`底下的每日抓取腳本（產出逐股的三大法人/
     融資融券/股權分散/借券JSON），不是「接上既有JSON」這麼簡單。
  2. **會撞到已知的PAT地雷**：這個新抓取步驟要掛進
     `.github/workflows/market.yml`，但這個repo的GitHub PAT沒有
     `workflow` scope，任何commit觸及`.github/workflows/*.yml`都會被
     GitHub拒絕push（見`research/MARATHON_STATE.md`2026-08-26第102輪
     記錄）——處理方式沿用既有慣例：workflow檔案的修改留在working tree
     不commit，其餘檔案正常commit，等使用者換有workflow scope的PAT再
     由使用者自己補上那個步驟。
  3. 均價試算（三大法人累計淨買×當日均價估算成本均線）依賴上面的逐股
     三大法人資料先有，是接在這個地基之後的第二層工作。
  4. 千張大戶持股比例（`TaiwanStockHoldingSharesPer`）跟借券賣出目前
     這個repo完全沒有既有的抓取邏輯可以參考，需要從FinMind/TWSE官方
     端點原地開工（依`CLAUDE.md`資料原則：先試主來源→備援→由已有欄位
     推導，三條都試過再誠實標「卡資料」）。

  **暫緩理由**：今晚已經有兩次背景agent反覆卡在混淆狀態、零進度燒了
  超過300萬token（App功能掃描、B29第一次嘗試），改用全新（非fork）
  agent後B29狀況好轉但還在跑。這個籌碼任務範圍比B29更大、更多未知數
  （4種新資料型態+workflow地雷+UI+成本均線估算），倉促再開一個大戰場
  風險偏高。**先不派工，留給下一輪session或使用者醒來後決定要不要
  拆更小的單位分批做**，這裡的查證筆記留給接手的人，不用重新摸索。

  原始指令全文：

  > 【指令開始】App 台股新增「籌碼」分頁（免費層今晚做，分點層登錄待付費決策）
  >
  > 一、免費籌碼層（現有/免費資料源，今晚建）
  > 1. App 台股個股新增「籌碼」區塊：三大法人買賣超趨勢(外資/投信/自營，可累計)、
  > 融資融券變化、股權分散/千張大戶持股比例週變化(TaiwanStockHoldingSharesPer)、
  > 借券賣出。
  > 2. 均價試算(免費版)：用三大法人累計淨買×當日均價，估算主力「成本均線」，
  > 畫在個股走勢圖上；明確標「估算、非精確成本」。
  > 3. 資料走既有排程 Actions→JSON、資料源禮儀、找不到誠實空狀態不塞假資料。
  >
  > 二、分點層——登錄 BACKLOG「卡付費資料源、待使用者決定」，今晚不做
  > 1. 券商分點進出、關鍵分點、特定券商(秘密買賣超)、分點均價：註明免費拿不到
  > (FinMind sponsor 付費 / 永豐無分點 / TWSE 狂爬觸封鎖+ToS灰色)，可行選項是
  > 付費(FinMind sponsor 或 富果分點 API)，等使用者決定是否付費再啟動。
  > 2. 不得為了有畫面而用非分點資料假裝成分點。
  >
  > 三、驗證紀律(寫進設計)：籌碼類訊號(尤其分點跟主力)屬擁擠且爭議方法，
  > 未來要走 signal_ledger 校準「能否預測扣成本後報酬」，App 顯示標「非投資建議、
  > 跟大戶不等於獲利、大戶也可能出貨」。
  >
  > 動 index.html→smoke 全綠才 commit；全程繁體中文；排在隔夜其他項之後、不影響馬拉松。
  >
  > 【指令結束】

---

## 佇列（2026-09-02凌晨，隔夜批次進行中收到，使用者原話全文，排在隔夜
批次之後處理，使用者自己也明講「排在其他隔夜項之後、不影響馬拉松」）

- [x] **App 兩個 UX 問題排進今晚（線圖不顯示 + 數字不會跳動）**——**已完成
  （2026-09-02凌晨，同一個background agent做完）**，分三個獨立commit：
  ①圖表診斷（5類圖表逐一實測，4類正常、1個真bug已修好：櫃買指數
  sparkline漏傳欄位，見`BACKLOG.md`「圖表逐一診斷」條目）②smoke test
  新增check 16「圖該顯示卻空白」防線③數字盤中自動輪詢（15秒定時+
  flash-up/flash-down閃爍動畫+誠實標示，**標⚠**因為本機開發時是非交易
  時段、用monkeypatch模擬驗證，還沒機會在真實開盤時段肉眼確認，見
  `BACKLOG.md`「App數字盤中自動輪詢」條目）。`.rise`/`.grow`如提醒沒有
  被誤用，改新增獨立的`flash-up-kf`/`flash-down-kf`。`node scripts/
  smoke_test.mjs`全數PASS，三個commit都已push。

  原始指令全文：

  > 【指令開始】App 兩個 UX 問題排進今晚（線圖不顯示 + 數字不會跳動）
  >
  > 一、線圖不顯示：全面診斷+修復
  > 1. 逐一檢查所有圖：個股走勢圖、大盤/類股 sparkline、選股成績單曲線、策略監控台
  > 權益曲線、籌碼趨勢圖等。對每個圖判定根因：資料缺 / 渲染壞(JS或SVG) / SW快取
  > 吃到舊版——三種分開處理，別一律當同一種。
  > 2. 用 Playwright 在 393×852 逐頁截圖，確認每個圖「真的有畫出線」，不是只驗有元素。
  > 3. 跟那條「資料新鮮卻顯示無資料 = FAIL」的 smoke 防線一起，把「圖該顯示卻空白」
  > 也納入冒煙測試。
  >
  > 二、數字盤中自動跳動（前端自動輪詢，不是真逐筆串流）
  > 1. 前端加盤中自動輪詢：台股/美股各自在其開盤時段，每約 15 秒自動重抓對應報價
  > JSON(quotes_sinopac/quotes_ibkr/…)、更新畫面數字，不用使用者手動下拉。
  > 2. 數字變動時套既有漲跌動畫(rise/grow tokens)紅綠閃爍，讓變化看得見。
  > 3. 非盤中停止輪詢(省資源)、顯示「已收盤」。
  > 4. 誠實標示：這是「近即時輪詢」，快慢受後端寫檔頻率限制，非逐筆 tick。
  > 若之後要更即時，另立項目做後端持久串流寫檔(較大工程)，本輪不做。
  >
  > 動 index.html→smoke 全綠才 commit；全程繁體中文；排在其他隔夜項之後、不影響馬拉松。
  >
  > 【指令結束】
