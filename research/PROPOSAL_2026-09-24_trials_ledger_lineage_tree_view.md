# PROPOSAL 2026-09-24：TRIALS_LEDGER 父子關係樹狀視圖（App 功能提案）

**狀態：只提案，不實作。** 依 `PENDING_QUEUE.md`【value_board 翻案處理＋轉向.一
候選名單定案＋FinLab 借鏡登記】登記.一②交辦，本文件是唯一交付物；核准前不寫
任何程式碼、不動 `index.html`。

## 背景

`TRIALS_LEDGER.md` 目前有 395 筆試驗，其中相當比例是同一個假設的「重測／修正版」
（例如 `weinstein_alpha_gate` → `weinstein_alpha_gate_engine_fix_recheck`，
`spillover_overlay_v1` → `spillover_overlay_v1_o2c`）。備註欄目前用「父筆
#346/#386」這種文字手動標註血緣，但沒有結構化欄位、也沒有任何檢視工具，讀者要
自己在文件裡搜尋才能拼出一條假設的完整演化過程（原始判定→發現 bug→修正後
重跑→判定是否翻轉）。

## 提案內容

在 App（`index.html`「日誌」分頁，或新增子分頁）新增一個 TRIALS_LEDGER 父子關係
樹狀視圖：

1. **資料來源**：`TRIALS_REGISTRY.jsonl`（結構化登記，起於 #187）新增一個選填
   欄位 `parent_id`（int 或 int 陣列，支援多父筆，例如 spillover_overlay_v1_o2c
   同時是 #346 與 #386 的子筆）。#187 之前只有 `TRIALS_LEDGER.md` 的非結構化文字
   備註，無法回填，樹狀視圖對這些舊筆只能以孤兒節點（無父）方式顯示。
2. **顯示方式**：每個節點顯示試驗編號、名稱、判定（PASS/FAIL/CHEAP_PASS/
   EXPERIMENTAL/未結案，依既有色碼）、關鍵數字（沿用備註欄已有的核心指標，例如
   VAL alpha p 值、percentile）。子節點縮排顯示在父節點下方。
3. **退步節點照樣保留**：若子筆判定比父筆更差（例如父筆 CHEAP_PASS、子筆重測後
   FAIL），節點依然顯示在樹裡，不得因為「結果變差」就隱藏或標記為不重要——這
   呼應 `CLAUDE.md`「復盤原則：流程重於盈虧」，退步結果本身是有效資訊。
4. **唯讀**：純顯示既有帳本內容，不提供任何編輯功能，避免 App 端意外成為
   TRIALS_LEDGER 的第二個寫入來源（違反單一事實來源原則）。

## 影響

- 新增欄位 `parent_id` 是選填、向後相容，不影響 `trial_registry.py --check` 現有
  的必填欄位檢查邏輯；需要在 `register_trial()` 簽章新增一個選填參數。
- 未來每次登記帶血緣關係的重測試驗時，需要記得填 `parent_id`，否則樹狀視圖看到
  的仍是孤兒節點——這是持續性的人工紀律成本，不是一次性工作。
- 不影響任何既有判定或關卡邏輯，純資訊呈現層。

## 風險

- `parent_id` 若填錯（例如填成兄弟筆而非父筆），樹狀結構會誤導讀者；建議
  `trial_registry.py --check` 增加一個非阻塞警告：`parent_id` 指向的編號必須
  存在且日期早於自己，格式錯誤才擋（未通過此檢查不阻擋既有的『非0不准commit』
  規則，只加一行 WARN）。
- 舊筆（#1~#186，非結構化年代）無法回填 `parent_id`，樹狀視圖對這段歷史仍是
  平面列表，這是資料本身的限制，不是實作可以解決的。

## 需要總司令裁示的點

是否核准實作（含 `TRIALS_REGISTRY.jsonl` schema 新增 `parent_id` 欄位、
`register_trial()` 簽章變更、App 端新視圖）。核准前維持現狀，不動工。
