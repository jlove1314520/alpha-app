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
