# PAPER_TRADING_ARCHITECTURE.md — 策略紙上前測系統架構規格（2026-08-25 使用者交辦）

**這份文件的作用**：使用者要求「策略紙上前測系統」——App「交易」頁的「策略」分頁，未來要顯示已上架策略的即時前測績效。**目前沒有任何策略通過完整驗證（含 holdout），所以這輪只做架構跟空狀態畫面，不放任何示範/假績效**（使用者原話：「不要放任何假的示範策略或假績效」）。這份文件把架構寫清楚，等真的有策略通過驗證時，直接照這裡的規格接資料，不用重新設計。

---

## 1. 上架條件（鐵律，不能放寬）

**只有通過馬拉松完整驗證（`MARATHON_PROTOCOL.md` 的便宜關卡1a + 深挖1b，且已經走完 holdout 解鎖流程）的策略才可以上架。** 目前沒有任何策略滿足這個條件：

- `weinstein_stage2_unbiased`：train/val 全過，但 alpha/beta 顯著性關卡還沒做完（見 `WEINSTEIN_ALPHA_GATE_TASK.md`），holdout 從未解鎖。
- `fut_basis_carry`：深挖(1b) 已判樣本外 FAIL，不合格。
- 其餘所有候選：連便宜關卡都還沒全過，或已經 FAIL。

**上架前必須具備**：holdout 已解鎖（`is_holdout_consumed()==True`，且是使用者明確授權解鎖的，不是馬拉松自己解鎖）、有明確的進出場規則（不是模糊的「因子排序」）、有風控參數（單筆風險%、最大部位數、kill switch 條件）。

## 2. `alpha-app/data/paper_trades.json` 格式

```json
{
  "schema_version": 1,
  "generated_at": "2026-08-25T09:00:00+08:00",
  "strategies": [
    {
      "id": "weinstein_stage2_unbiased",
      "name": "Weinstein 第二階段突破（無偏宇宙版）",
      "market": "TW",
      "listed_date": "2026-09-01",
      "paper_start_date": "2026-09-01",
      "description": "...",
      "entry_rules": "...",
      "exit_rules": "...",
      "risk": {
        "per_trade_risk_pct": 1.0,
        "max_positions": 5,
        "kill_switch": "單日虧損達帳戶2%立即停止當日訊號產生"
      },
      "invalidation": "此策略假設...一旦...條件不成立，此策略應視為失效，不應繼續紙上前測或轉正",
      "metrics": {
        "cum_return_pct": 0.0,
        "mdd_pct": 0.0,
        "sortino": null,
        "n_trades": 0
      },
      "current_position": null,
      "trades": []
    }
  ]
}
```

`strategies` 目前是空陣列 `[]`。App 前端讀到空陣列時顯示「目前無上架策略，等待驗證通過」，不顯示任何卡片。

## 3. 每筆交易紀錄格式（`trades` 陣列內）

```json
{
  "signal_generated_at": "2026-09-02T08:30:00+08:00",
  "signal_date": "2026-09-02",
  "code": "2330",
  "side": "buy",
  "signal_price_ref": null,
  "settle_date": "2026-09-03",
  "settle_price": null,
  "settled_at": null,
  "status": "pending"
}
```

**`status` 只能是三種之一**：`pending`（訊號已產生，尚未到隔日結算）、`settled`（已用隔日實際價格結算）、`closed`（部位已出場）。

## 4. 鐵律：事前產生、絕不事後回填（這是使用者原話明確強調的一條）

> 訊號必須「事前」產生並寫入 `paper_trades.json`（含時間戳），絕不可事後回填或重算。每日排程產生當日訊號 → 記錄 → 隔日以實際價格結算。

具體規則：

1. **訊號產生時間必須早於當天市場開盤**（`signal_generated_at` 這個時間戳要能證明這一點），且訊號一旦寫入就不可修改（append-only，跟 `TRIALS_LEDGER.md`/`REPORT.md` 同樣的紀律）。
2. **`signal_price_ref` 在訊號產生當下必須是 `null` 或收盤前無法得知的值**——不能拿當天盤中或盤後的價格回頭填進「訊號當時的參考價」，那等於用未來資訊污染訊號本身。
3. **結算永遠用「隔一個交易日」的實際成交價**（`settle_price`），不能用訊號當天的價格結算（那樣等於訊號產生當下就已經知道會不會成交，不是真正的前瞻測試）。
4. **任何一筆交易的 `status` 從 `pending` 變成 `settled` 之後，這筆記錄不可再修改**（除非是修 bug，且要留下修改前後的完整記錄，比照 `TRIALS_LEDGER.md` 的「不覆寫、只加註」精神）。
5. 這條紀律的意義：如果違反（例如今天心血來潮想到一個策略，回頭用歷史資料「回填」過去幾個月的訊號紀錄），那些績效數字就是用未來資訊算出來的，不是真正的前瞻測試，等於自己騙自己——這正是「紙上前測」這個機制存在的意義，一旦破功，整個系統就沒有驗證力道。

## 5. 每日排程流程（架構規格，尚未實作出實際排程腳本——目前沒有任何策略需要跑）

```
盤前（開盤前）：
  1. 讀取已上架策略清單（paper_trades.json 的 strategies）
  2. 對每個策略，用「凍結的」進出場規則（不可臨時調整參數）算出今天的訊號
  3. 把訊號 append 進對應策略的 trades 陣列，status=pending，signal_generated_at 蓋上此刻時間戳
  4. commit + push（讓時間戳有 git commit 時間佐證，類似 TRIALS_LEDGER.md 的紀律）

隔一個交易日（盤後）：
  5. 抓實際成交價，把上一批 pending 的訊號結算成 settled
  6. 更新該策略的 metrics（cum_return_pct/mdd_pct/sortino/n_trades，用已結算的交易重新算）
  7. commit + push
```

這個排程腳本（比照 `alpha-data/compute_margin_maintenance.py` 或研究馬拉松的 `run-marathon-cycle.ps1` 模式）**這輪沒有寫**，因為目前沒有任何策略滿足上架條件、沒有東西可以跑。等第一個策略通過 holdout 解鎖流程，才需要真的把這個排程腳本生出來、掛進 Windows 工作排程器。

## 6. App 前端行為

- `data/paper_trades.json` 的 `strategies` 為空陣列時：顯示「目前無上架策略，等待驗證通過」的空狀態卡片，不顯示任何策略資料。
- 若未來有策略上架，每個策略卡顯示：策略名、上架日、市場（台/美/期）、紙上前測起始日、累計報酬、MDD、Sortino、交易筆數、目前部位；點進去可看完整說明：策略說明、進出場規則、風控、失效情境。
- 全區固定顯示「⚠ 紙上模擬，非真實交易，非投資建議」。
