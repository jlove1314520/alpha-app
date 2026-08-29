# MARATHON_LOG.md — 自主研究馬拉松可見心跳（2026-08-29啟動）

**這份檔案存在的理由**：使用者裁示「解決使用者『看不到它在跑』——每完成
一個關卡或每約30分鐘寫一行（時間戳＋現在在跑哪條假設的哪一關＋結果），
並commit push」。最新的寫最上面。

**授權範圍**：從checkpoint `c19c11f`接續，照`research/HYPOTHESIS_QUEUE.md`
排隊執行，先還B24可重現性乾淨重跑這筆前置債，然後Weinstein第二階段→
CTA趨勢跟隨→PEAD組合層→股票股利率carry→（regime overlay/量價/低波/
類股輪動依相依性到位再跑）。只有「要不要拉到1000draws」「survivorship-free
宇宙要不要投入」「任何不可逆操作/花錢」這三種情況才停下來問，其餘自主
往下跑。

---

## 2026-08-29T04:45+08:00 — Weinstein v2結案：FAIL（隨機控制組+成本敏感度雙雙不過）

第2/4關跑完。**判定：FAIL，移入`STRATEGY_GRAVEYARD.md`，不進第3/5/6/9
關**。關鍵數字：
- VALIDATION：表面總報酬+56.72%贏買進持有(+54.58%)，但拆解後beta貢獻
  +32.93%占過半，純alpha僅+23.80%（配對式隨機控制組n=200中位數
  +21.31%，**percentile=55.0，遠低於90.0單測門檻**）。成本敏感度：1x
  alpha+23.80%→2x+4.79%→**3x轉負-16.37%**。
- TRAIN：純alpha本身就是負的（-3.66%，beta貢獻+19.11%比總報酬
  +15.45%還高）。隨機控制組percentile=84.0，同樣未達門檻。成本敏感度
  3x：alpha-31.97%、**總報酬也轉負-19.65%**。

**這是`CLAUDE.md`「復盤原則：流程重於盈虧」點名的典型案例**——表面
總報酬好看（贏買進持有），拆解後發現主要是beta曝險而非真alpha，且
alpha經不起真實成本壓力測試。完整數字寫進`STRATEGY_GRAVEYARD.md`，
`HYPOTHESIS_QUEUE.md`#1標記結案，`data/strategies.json`的
`weinstein_stage2_baseline`狀態自動從`草稿`升級為`回測未通過`（新增
`generate_strategies_json.py::_graveyard_heading()`動態檢查
`STRATEGY_GRAVEYARD.md`是否有對應條目，不是手動改）。**明確不泛化**：
這只是這個具體實作（60日相對強度窗口+150日均線+TAIEX 200日均線閘門）
的死法，不代表Weinstein第二階段概念本身沒用。

**立即接續**：佇列#2 CTA趨勢跟隨（期貨，時序動量），開始第1關sanity。

---

## 2026-08-29T04:05+08:00 — Weinstein v2抓到真bug並修好：0筆交易→有效交易

執行第2/4關（`weinstein_v2_alpha_gate.py`）第一次跑，發現TRAIN/
VALIDATION**兩期都是0筆交易**——追查發現`stage2_signal_v2()`假設
`price_data`已經有相對強度欄位（沿用sanity階段用的`factor_ic.py`快取
現成的`f_rel_strength`），但這支campaign腳本走的是不同資料路徑
（`adjusted_price_series()`直接載入，不經過`factors.py::prepare_
factors()`），那個欄位根本沒被算過，每天每檔都被誤判「資料缺失」跳過。
**這是sanity階段測試涵蓋率不足的真實案例**：sanity PASS了，但測的
不是後續關卡實際會用的資料載入路徑。

修法：新增`prepare_price_data_v2()`獨立計算相對強度（60日個股報酬−
60日大盤報酬，跟`factors.py::f_rel_strength`同一個定義，不依賴外部
欄位是否存在），三支消費端腳本（sanity/run_weinstein_unbiased_v2/
weinstein_v2_alpha_gate）全部改用同一個函式。sanity重跑數字不變
（仍PASS），確認bug只在campaign腳本的資料路徑，不影響sanity本身的
判定方向。

修好後重跑：**VALIDATION期353筆交易，+56.72%報酬，贏過買進持有
（+54.58%）；TRAIN期515筆交易**，第2/4關（n=200隨機控制組+成本敏感度+
alpha/beta拆解）背景執行中，已設置Monitor，會持續更新這裡。

---

## 2026-08-29T03:40+08:00 — B24乾淨重跑完成：判定結論穩健但發現新的非決定性來源

B24可重現性乾淨重跑跑完了。**判定結論一致**（兩次獨立跑法都是不及格：
兩期都贏買進持有+贏全部100次隨機對照組，但兩期alpha都不顯著）——但
**精確數字不是逐位元相同**（TRAIN報酬75.87%→71.79%，MDD -19.95%→
-27.85%）。深入比對兩份log發現根因：**不是快取寫入損毀**（那個bug已經
用atomic write修好，`determinism_self_test.py`本輪兩次獨立確認PASS），
是**FinMind額度即時狀態導致每次跑因子完整度不同**（原始跑1908次因子
跳過、乾淨重跑1461次，次數本身就不一樣）——這是一個新發現、目前還沒解
的非決定性來源，跟已修好的問題是不同機制。完整分析寫進
`B24_RESULTS.md`「可重現性乾淨重跑」章節，`data/strategies.json`的
`value_board_v2.limitations`也同步更新。**這不在使用者的三個停下清單
裡（不是1000draws/survivorship-free/不可逆操作），誠實記錄+登錄下一步
建議後繼續往下跑，不停下等待**。

**B24前置關卡狀態：判定結論確認穩健，可以繼續信任佇列後續的「通過」
判定**——質化結論（及格/不及格）在兩次獨立跑法之間一致，這是「儀器
不穩=不能信」這條最高投資原則要求的最低標準，已經達到；精確數字的
不可重現性是另一個獨立問題，已誠實登錄，不阻擋佇列繼續往下走。

**立即接續**：CPU資源現在空出來了，馬上執行Weinstein v2第2/4關
（隨機控制組n=200+成本敏感度，`weinstein_v2_alpha_gate.py`）。

---

## 2026-08-29T02:55+08:00 — B24乾淨重跑背景執行中；Weinstein v2第1關(sanity)PASS

**B24可重現性乾淨重跑**：`determinism_self_test.py`重跑一次確認Test A/B
仍PASS（bit-identical）。用`CACHE_SUFFIX=_clean`環境變數（新增到
`run_value_board_v2_pit_backtest.py`，不影響預設行為）強制建一份100%在
atomic write修法（`c97ac0f`）之後建置的全新快取，背景執行中
（`pit_run_liquidity500_clean.log`），已設置Monitor持續盯。

**Weinstein第二階段v2**（`HYPOTHESIS_QUEUE.md`#1，佇列第一條）：
- 新增`strategies/weinstein_stage2_v2.py`（不改v1，避免動到
  `TRIALS_LEDGER.md`#10/#11引用的既有結果）：三個gate（站上150日均線+
  均線上揚+`f_rel_strength`>0），排名依相對強度。
- **第1關sanity：PASS**——40個季度檢查點，通過gate股票池
  mean=95.2/median=107.0（486檔候選，合理），事後20日報酬通過gate組
  +2.24% vs 全樣本+1.41%，方向正確。
- 第2關（隨機控制組n=200）+第4關（成本敏感度1x/2x/3x）程式碼已就緒
  （`strategies/run_weinstein_unbiased_v2.py`+`weinstein_v2_alpha_gate.py`，
  複製v1既有基礎設施只換訊號函式），**刻意先不執行**——避免跟B24乾淨
  重跑同時搶CPU（B24-500那輪實測到102秒/draw的CPU競爭拖慢，這次要避免
  重演）。等B24乾淨重跑完成、收到背景任務完成通知後，立刻接著跑這支。

**下一步**：等B24乾淨重跑完成通知 → 記錄B24最終確認結果（含跟原本
100-draws結果的一致性比對）→ 立即執行`weinstein_v2_alpha_gate.py`
（第2/4關）→ 依結果決定PASS進監控台或FAIL進GRAVEYARD、或需要第3/5/6/9
關補強 → 接著CTA趨勢跟隨。

---

## 2026-08-29T02:10+08:00 — 馬拉松啟動，開始B24可重現性乾淨重跑

從checkpoint `c19c11f`接續。目前佇列狀態：`HYPOTHESIS_QUEUE.md`8條全部
未起跑，`STRATEGY_GRAVEYARD.md`只有3筆回溯整理。

**第一步（前置關卡）**：B24可重現性乾淨重跑。既有的
`value_board_v2_sample_cache_liquidity500.pkl`（2026-08-29 00:38建立）
建置時間橫跨atomic write修法commit（`c97ac0f`）前後，不能100%確定沒有
受並行讀寫影響——即使那輪跑完沒有崩潰/讀取錯誤。這次改用全新快取檔名
`value_board_v2_sample_cache_liquidity500_clean.pkl`（不覆蓋/不刪除舊檔，
純粹確保這次建置100%發生在atomic write修法之後），重跑：
1. `determinism_self_test.py`（Test A+Test B）——先確認機制本身仍然
   健康。
2. 全新快取建置 + B24-500完整流程（TRAIN+VALIDATION兩期、各100次
   隨機對照draws）。

背景執行中，預估耗時跟上一輪相近（factor prep~20分鐘+約6~7小時的
draws），會持續更新這裡。
