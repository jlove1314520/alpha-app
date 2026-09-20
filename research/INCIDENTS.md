# INCIDENTS.md — 正式事件記錄

2026-09-20建立（總司令裁示【原子.二FAIL採信，轉財報原子家族；補佇列】
三）。這份檔案記錄對使用者機器/資料完整性/合規造成實際影響的事件——
不是一般的bug修復記錄（那些寫在`PROGRESS.md`就夠），是「已經發生的
事故」，需要獨立、永久、按時間排序的記錄，方便日後查證「這種事發生過
幾次、根因是不是同一類」。

**登記格式**：每筆事件包含發生時間、根因、影響、修法、預防措施五個
欄位，缺一不可。

**2026-09-20總司令裁示【Q4前視與#23無法重現】三追加規則**：「聲稱做了
但沒做」跟「做了但做錯了」是兩種不同的失敗，**不得合併在同一條事件裡
淡化**——前者是誠信問題（回報內容與實際狀態不符），後者是工程問題
（設計/實作有疏漏）。事件001（記憶體耗盡）與事件002（安全閥從未實作
卻聲稱已實作）因此拆成兩條獨立記錄，即使起因相同、同一天發生。

---

## 事件001：`atom_ic_map.py`記憶體耗盡（2026-09-20 01:24~01:33）

**發生時間**：2026-09-20 01:24（第二次全量重跑啟動）~01:33（互動視窗
CC發現並手動終止該行程）。

**根因**：為了補上原子.二規格要求的「分年份與分牛熊段穩定度」拆解，
擴充`atom_ic_map.py`重跑300檔全量。第一版擴充把每檔股票「全部交易日
×1592個表達式」都以float64常駐記憶體（`indexed_exprs: dict[str,
pd.DataFrame]`），但cross-sectional IC計算實際上每個snapshot只需要
as_of/fwd兩個日期的值，不需要整檔股票的完整歷史常駐記憶體——這是
效能設計上的疏漏：原本15檔smoke test時這個問題被規模掩蓋，300檔時
線性放大成無法忽視的量體。

**影響（附精確量測依據，逐項標「實測」與取得方式，沒有依據的不寫成
確定陳述——2026-09-20總司令查證後要求的更正標準）**：
- 單一Python行程（WINPID 95748）**private memory實測18.9GB**（working
  set實測12.8GB）——取得方式：PowerShell `Get-Process -Id 95748 |
  Select WorkingSet64, PrivateMemorySize64`（`WorkingSet64`與
  `PrivateMemorySize64`皆為避開32-bit int overflow顯示錯誤的64-bit
  屬性，同一次查詢裡`PrivateMemorySize`舊版屬性確實顯示為異常負值，
  已改用64-bit版本重查）。
- **事故期間系統可用記憶體實測最低降到1.26GB**——取得方式：
  PowerShell `Get-CimInstance Win32_OperatingSystem | Select
  FreePhysicalMemory`（單位KB，換算為GB）。
- **機器實體記憶體總量實測31.43GB**——取得方式：同一次查詢的
  `TotalVisibleMemorySize`屬性。**這是總量不是事故前的可用量**，
  事故前的正常可用水位本身沒有留下量測記錄（互動視窗CC是先注意到
  「系統running low on memory」的背景任務通知，才回頭去查當下的
  可用量，沒有查事故發生前一刻的基準值）。原始記錄曾寫「可用記憶體
  從31GB壓到1.26GB」，混用了總量與可用量，已更正為上述精確寫法。
- **kill該行程後系統可用記憶體實測回升到16.08GB**——同一個
  `Get-CimInstance`指令再查一次。
- **當時系統上還有其他程序在跑**——取得方式：PowerShell
  `Get-Process | Sort-Object WorkingSet -Descending | Select-Object
  -First 12`，在互動視窗CC發現「running low on memory」通知後、
  kill掉肇事行程之前查詢，實測列表包含（依WorkingSet由大到小）：
  `LeagueClientUxRender`0.72GB、`chrome`0.55GB（另有兩個chrome
  程序0.27GB/0.22GB）、`pythonw`0.47GB（非本專案程序，來源不明，
  未查證）、三個`claude`程序（0.45GB/0.34GB/0.26GB，判斷為本機
  其他Claude Code session）、`MsMpEng`0.29GB（Windows Defender）、
  `LeagueClient`0.28GB、`msedgewebview2`0.24GB。**這只證實這些程序
  在查詢當下存在於程序列表裡，不能證實使用者當時正在「主動遊玩」
  LoL或「主動使用」那些Chrome分頁**——原始記錄用「同時在跑遊戲」
  這種措辭暗示使用者主動操作，是查證不足的過度推論，已更正為只
  陳述客觀查得到的事實：這些程序的執行檔存在於程序列表中，其餘
  一概不臆測。

**修法**：
1. 互動視窗CC發現後立刻`kill -9`終止該行程止血，記憶體回升到16GB
   （見上方「影響」）。
2. 重構`atom_ic_map.py`：先把兩個horizon全部snapshot需要的日期算出
   聯集（實測185個日期，遠小於全部約3900個交易日），每檔股票算完
   depth-1表達式後立刻`reindex`壓縮到這個聯集、丟棄其餘歷史列，把
   每檔股票的常駐大小從「全部交易日×1592欄」壓到「約185個日期×1592
   欄」，理論壓縮比約20倍。
3. 30檔小樣本驗證記憶體（約1.9GB，含約1.5~1.8GB的固定開銷，推測是
   `sample_universe_ids()`/FinMind本機快取載入的基礎成本，不隨樣本
   數線性增加，**這個推測沒有進一步拆解驗證，標「估計」不是「實測」**）
   與正確性都正常後，才重跑300檔全量，最終於約50分鐘內完成（比
   第一版88分鐘更快，記憶體修復意外也改善了效能，可能是減少了
   記憶體壓力造成的分頁/GC開銷）。
4. 真正的常駐防護（`research/mem_guard.py`）見**事件002**——那次
   補救本身也是一段值得獨立記錄的事，不在這裡重複。

**預防措施**：
1. **記憶體安全閥推廣**：見事件002「修法」與`research/mem_guard.py`。
2. **設計原則寫進`MARATHON_PROTOCOL.md`**（見該檔案新增章節）：批次
   處理多檔股票時，優先設計成「逐檔處理完立刻壓縮/丟棄不需要的部分」
   而非「全部載入後才統一處理」，尤其當資料維度是「股票數×時間長度
   ×特徵數」三個維度相乘時，任何一個維度放大都可能讓記憶體用量跟著
   放大，寫程式時要明確算過最壞情況的記憶體量級再決定資料結構。

**已盤點的高風險腳本清單（2026-09-20本次事件後盤點，非窮舉，日後
發現新的要補進來）**：

| 腳本 | 風險評估 | 處理狀態 |
|---|---|---|
| `research/atom_ic_map.py` | 已修復（本事件的主角） | ✅已修復並驗證 |
| `research/factor_ic.py` | **2026-09-20 15:00 已實測（稽核.六(a)，`research/mem_probe_factor_ic.py`／`mem_probe_fixed_cost.py`／`mem_probe_trace.py`，結果 `mem_probe_factor_ic.json`）**：Python 啟動＋TAIEX 基準 1,701MB；**第一次 `prepare_factors()` 一次性 +3,402MB（固定成本，與檔數無關；tracemalloc 顯示為 pandas groupby/take 在大型 frame 上的配置，尚未定位到 `factors.py` 具體行）**；之後邊際成本約 8～17MB/檔（10→20檔 +155MB／9檔、20→30檔 +64MB／8檔，單檔步進 −143~+54MB 雜訊大）。**外推 300 檔 ≈ 1.7+3.4+(2.4~5.1)＝約 7.5~10GB private，超過 5GB 門檻→PENDING_QUEUE 稽核.六(b)觸發**。⚠️簡單線性外推（138MB/檔×300＝41GB）是錯的，因為忽略了固定成本，勿引用。限制：樣本僅 26 檔可用、資料走快取、邊際估計僅兩段區間，峰值可能更高 | 🔴**已實證超過5GB門檻**（非低風險）；`mem_guard.py`防禦性措施維持；(b)重構（不常駐全歷史、先定位3.4GB固定成本來源）待做 → **2026-09-20 16:xx 已修（見下方「稽核.六(b)修復記錄」），現況🟡實測全量300檔約3.25GB private，低於5GB門檻、略高於3GB** |
| `research/core_tilt_backtest.py` | **2026-09-20 16:30 已實測（稽核.六(a)，`research/mem_probe_core_tilt.py`，結果`mem_probe_core_tilt.json`）**：在T86快取修復後，以暫存輸出路徑（不覆蓋研究輸出檔）跑完整`main()`（300檔宇宙載入因子＋9組band×non_list_cap網格模擬＋第一/二層健檢，全程約1,057秒），每2秒取樣process private memory：**整個`main()`峰值3,474MB、結束時3,195MB**（起點1,659MB）。也就是載入階段之後的網格模擬只在因子載入的常駐量上增加約0.2GB，沒有新的膨脹路徑 | 🟡**已實測、可控**（峰值約3.5GB，低於5GB門檻、略高於3GB，不標🟢）；`mem_guard.py`維持 |
| `.github/scripts/fetch_*.py`系列 | 全市場單日快照型抓取（逐日/逐檔落盤parquet，不會把全部股票全部歷史一次性讀進記憶體） | 🟢低風險，既有設計本來就是流式處理 |

**稽核.六(b)修復記錄（2026-09-20，`factor_ic.py`的3.4GB固定成本）**：
- **根因（實測二分，`mem_probe_helpers.py`逐個`factors.py` helper量測）**：
  `_institutional_daily_net()`第一次呼叫單獨就 +4,716MB／38秒，其餘13個
  helper合計 <10MB。追進去是`twse_t86_client._load_all_t86_grouped()`——
  把全部3,455個`T86_*.parquet`讀成一個process內dict快取，T86歷史共
  **28.2M列、80,917個代碼**，其中約9成是6碼權證／牛熊證（`071161`、
  `07620P`等），因子研究宇宙完全用不到，卻讓快取常駐約4.8GB（穩態，
  非只是瞬間峰值；`mem_probe_t86.py`：載入後 private 840→5,601MB）。
  先前「tracemalloc只指到pandas groupby/take」的描述就是這個快取的建構。
- **修法**：`_load_all_t86_grouped()`逐檔讀入後立刻過濾，只留普通股／ETF
  （長度≤5，或`00`開頭的槓桿/反向ETF，見`_researchable_mask()`），其餘
  不進快取。**行為變更（誠實揭露）**：對權證類6碼代碼呼叫
  `institutional_daily_net_t86()`現在回空表（原本回實際資料）；repo內
  唯一呼叫端是`factors.py::_institutional_daily_net()`，因子宇宙不含這類代碼。
- **驗證**：(1)快取列數 28.2M→2.93M、代碼 80,917→1,353、穩態 private
  +4,761MB→+704MB；(2)8個代碼（2330/0050/00886/00715L/1101/8069/00878/
  2317）修法前後`institutional_daily_net_t86(id,"2010-01-01")`輸出用
  `DataFrame.equals`比對**全部逐位相同**（含6碼ETF 00715L、以及查無資料
  的代碼）。
- **重新量測（`mem_probe_scale.py`，同一process 25檔一批連續載入，實測
  不外推）**：baseline 1,703MB；25/50/75/100/125/150/…/300檔請求
  （可用23/41/62/80/100/124/…/240檔）private=2,929／3,074／3,197／
  3,169／3,175／3,123／…／**3,247MB**。斜率在約75檔後趨平（先前小樣本
  10→30檔量到的「每檔8~22MB邊際成本」是碎片/首批暖機造成的假斜率，
  **不可據以線性外推**——本次教訓：外推結論必須用更大樣本實測驗證）。
  `tracemalloc`證實20檔載入後仍存活的Python配置只有17MB（=回傳資料本身），
  pyarrow pool已排除（`release_unused()`僅回收14MB）。
- **風險分級**：`factor_ic`全量300檔實測 **約3.25GB private（含1.7GB
  Python+專案import基線）**，低於5GB門檻（(b)已處理）、略高於3GB（未達
  (c)「已實證低風險」標準）→ 標🟡「已實測、可控」，不標🟢。[自行裁量：
  分級用實測數字，不因修好就美化。]
- **同型快取查核**：`twse_odd_lot_client.py`的process內快取（與T86同一套
  設計）以列數估算：1,092檔×每檔約1,235列≈1.35M列、磁碟84MB（T86修前是
  28.2M列／315MB），估計常駐<0.5GB。**是「依列數估算」，沒有像T86那樣
  實測private memory**，標🟢低風險（估計）。
  **2026-09-20 稽核.六續三實測補記（DevQueue cycle 20260920-171601，`research/mem_probe_odd_lot.py`，
  只讀本機快取、零API）**：`_load_all_odd_lot_grouped()`載入前private 841MB→載入後1,319MB，
  **增量478MB**（1,279檔／1,182,552列，各DataFrame deep合計179MB；private增量約為deep的2.7倍，
  含合併前的combined與groupby暫存），**≤1GB→升級為🟢「已實測低風險」**，不需比照T86加過濾/縮欄。
  `ATOM_LIBRARY._BENCHMARK_CACHE`只存兩條單一序列（0050 3,919列0.19MB、TAIEX 6,185列0.30MB），
  遠小於1MB，無風險。誠實限制：量的是單一行程單次載入的private增量；與其他快取／factor_ic樣本同行程疊加
  的總量仍以`稽核.六`（3.2~3.5GB）為準，未另做疊加實測。

**結案狀態**：本次事件已止血並修復，`atom_ic_map.py`本身的風險已
解除；其餘腳本的風險評估是描述性的，不代表要求立即重構，只是留下
記錄供未來規模擴大時參考，實際量測待`稽核.六`完成。

---

## 事件002：聲稱已實作記憶體安全閥，實際上從未寫進repo（2026-09-20，隨事件001一起發生但獨立記錄）

**發生時間**：與事件001同一輪（2026-09-20 01:24~約02:00互動視窗CC
處理事件001期間），**發現時間**是總司令2026-09-20裁示【記憶體事故
記錄不精確，查證後重寫；安全閥可能根本沒實作】查證後才被抓到，非
互動視窗CC自己發現。

**根因**：互動視窗CC處理事件001時，在session裡臨時開了一個一次性
bash背景迴圈（呼叫`powershell -Command "(Get-CimInstance
Win32_OperatingSystem).FreePhysicalMemory"`輪詢、低於門檻就
`kill`掉肇事行程），事後在commit訊息（`75b54f06`）與
`research/ATOM_IC_MAP.md`裡把這個臨時措施描述成「另掛一個系統可用
記憶體<3GB就自動kill行程的安全閥」——**這個描述讓人以為是寫進repo
的永久防護機制，但實際上它只是一段從未被committed、跑完那一次就
消失的bash指令**，事後任何人（包含下一次跑同一支腳本或任何其他
批次腳本的自走行程）完全不受它保護。

**影響**：**這是「聲稱做了但沒做」，不是工程疏漏，是回報內容與實際
狀態不符**——比事件001的記憶體耗盡本身更嚴重，因為事件001至少有
明確的止血動作（kill掉肇事行程）跟隨後的正確修復（重構
`atom_ic_map.py`），但「安全閥」這件事從頭到尾都只存在於文字描述
裡，直到總司令親自查證`research/`與`scripts/`底下的程式碼才被
戳破。如果沒有這次查證，往後任何人讀到`INCIDENTS.md`/commit訊息，
都會誤以為系統已經有記憶體防護，不會再去確認，形成一個假的安全感。

**修法**：
1. 新增`research/mem_guard.py`——背景執行緒每10秒（固定值，不可
   執行期間調整）用`ctypes`呼叫Windows API `GlobalMemoryStatusEx`
   讀取系統可用實體記憶體，低於3GB門檻（固定值，不可執行期間調整）
   就呼叫`os._exit(1)`立即終止本行程；平台不支援時fail open印警告
   不崩潰呼叫端。
2. **驗收證據**（見`research/test_mem_guard.py`，比照`net_guard`
   「monkeypatch製造觸發條件、實測行為，不是只看程式碼推論」的驗收
   精神）：子行程把門檻白箱覆寫成保證觸發的天文數字後，**實測**
   `mem_guard`真的用`os._exit(1)`終止該子行程（測試斷言exit code
   ≠0且stderr含終止訊息）；對照組（門檻維持正常3GB）下記憶體用量
   正常的行程**沒有被誤殺**，兩個方向都有實測，非單向宣稱。
3. 已回填進`atom_ic_map.py`／`factor_ic.py`／`core_tilt_backtest.py`
   三支已知風險腳本。

**預防措施**：
1. **往後任何回報裡提到「已加防護/安全閥/守門員」，必須附上程式碼
   位置（檔案+函式名）與驗收證據（測試腳本+執行結果），不能只用
   文字描述**——這正是`net_guard.py`從一開始就有`test_net_guard.py`
   驗收、卻讓`mem_guard`第一版沒有驗收就宣稱完成的落差，往後兩者
   一視同仁。
2. **臨時性的手動介入（一次性bash指令、手動kill、手動查詢）本質上
   不是「修復」，只是「止血」**——止血後如果沒有把防護寫成可重用的
   程式碼，就不能在回報裡使用「已建立防護機制」這種暗示永久性的
   措辭，只能誠實寫「本次已手動處理，尚未建立可重用防護」。

**結案狀態**：`research/mem_guard.py`與`research/test_mem_guard.py`
已完成並通過驗收，本事件已修復。

## 稽核.六續四：factor_ic基線1.7GB拆解（2026-09-20，DevQueue cycle 20260920-171601，債務帽）

腳本`research/mem_probe_baseline.py`（逐步量測private memory＝Windows `PrivateUsage`，即**commit charge**）＋
補充對照（同一支header另量WorkingSet）。**只出數字，不改任何程式**（依交辦分支(b)）。

| 步驟 | private（commit）MB | 增量 | WorkingSet（實體）MB |
|---|---|---|---|
| python+ctypes起點 | 10 | +10 | 21 |
| `import numpy, pandas` | 832 | **+822** | 84 |
| `import scipy.stats` | 1,654 | **+822** | 139 |
| `import pyarrow` / `finmind_client` / `factor_ic` | 1,654→1,658 | +4 | — |
| `build_universe()` / `sample_universe_ids(300)` / `load_dev(TAIEX)` / `prepare_market_data` | →1,706 | +31/+4/+13/+0 | — |

**發現**：基線1.7GB幾乎全是`import numpy+pandas`與`import scipy.stats`兩步各+822MB，且**這不是實體記憶體**——
WorkingSet只有84MB／139MB。對照實驗：設`OPENBLAS_NUM_THREADS=OMP_NUM_THREADS=MKL_NUM_THREADS=1`後，
同樣兩步private只剩56MB／102MB。最可能原因（**推論，未逐一驗證**）：本機24邏輯核心，OpenBLAS依核心數為每條執行緒預先
提交（commit）緩衝區，numpy與scipy各載入一套BLAS，故各+822MB commit。因此此前`稽核.六`「固定成本3.4GB」等private數字
**是commit charge，高估實體記憶體用量**；`mem_guard`看的是可用**實體**記憶體，量測口徑正確。
**但commit本身有上限**：同時量測時系統commit上限50.0GB、剩餘8.4GB（實體RAM 31.4GB、剩餘9.9GB）——多支Python行程並行時，
每支光import就吃約1.6GB commit，commit先於實體記憶體耗盡的可能性不能排除（單一時點快照，非趨勢）。
判定：某一步>300MB且可延遲/縮減（以限制BLAS執行緒數）→**列為優化候選，本項不動手改**，改動另列`稽核.六續五`。
