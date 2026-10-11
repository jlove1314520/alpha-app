# B19 訊號管線骨架——事前登記規格（market-signal-vetting 方法）

- 登記日：2026-10-11（DevQueue cycle 20261011-140102，常備.開發-因子類-B19）
- 試驗名：`b19_signal_ledger_forward_v1`（track=TW）
- 依據：`BACKLOG.md` B19 五點規格、`docs/Alpha_新聞與供應鏈連動_設計小抄.md` 第三節（割韭菜偵測）
- **本檔在任何前瞻樣本產生之前 commit**；之後要改判準，只能另開 v2 並重新登記，不得回頭改本檔。

## 0. 這條試驗的性質（先講清楚，避免被誤讀成回測）

B19 規格第 4 點鐵律：訊號一律【事前】寫入 `data/signal_ledger.json`，T+5/T+20/T+60 由排程【只回填】，
**不得事後補建紀錄**。所以這條試驗**結構上沒有歷史樣本**——用 `events.json` 過去 90 天的重大訊息
重建一份「當時會寫進台帳的訊號」就是事後補建，等同回測，正是規格禁止的事。

依六關系列第 10 關（資料源歷史起點探測）：本台帳起點＝2026-10-11（第一次排程寫入），晚於
train/val 邊界 → 判「**只能前向觀察**」。GATE_SEQUENCE 第 1～9 關在樣本數達門檻前一律記「未能執行」，
不是 PASS 也不是 FAIL。

（重大訊息的歷史事件研究已由其他試驗做過，見 `research/material_news_car_gate*.py` 系列；本條測的是
「來源分層＋交叉驗證＋已反映偵測」這套**篩選流程**有沒有在前瞻資料上篩出超額報酬，不是重測重大訊息本身。）

## 1. 訊號來源（資料源查證）

| 層級 | 來源 | 現況 |
|---|---|---|
| L1 官方申報 | TWSE/TPEx 重大訊息（MOPS t05st01，`data/events.json`，`news_events.yml` 每 30 分鐘） | 已接 |
| L2 公司自述 | 公司 IR 新聞稿 | **未接**（缺口，無既有抓取器） |
| L3 專業媒體 | 中央社財經／Yahoo股市／經濟日報 RSS（`data/news.json`，只存索引） | 已接；`codes` 欄位有標的者才入帳 |
| L4 社群 | Reddit 等 | **未接**，屬 B21；L4 單獨出現不得影響評分，只能標「待驗證線索」 |

L1 事件類型只收：重大訂單、併購、處分資產、增減資、財務、訴訟、法說會。
排除：月營收／除權息（排程性、非訊息衝擊）、人事／其他／停復牌（資訊量低、雜訊大）。[自行裁量，理由同括號]

獨立來源計數：經濟日報三個 RSS（焦點／產業／證券）算**同一個**來源。

## 2. 交叉驗證（升格條件，規格第 2 點）

升格為 `status="訊號"` 需滿足其一：
- (a) 本身是 L1/L2，或同標的 ±3 個日曆天內有 L1/L2 事件；
- (b) 同標的 ±3 日內有 ≥2 個獨立 L3 來源；
- (c) 自有資料佐證——**本版未實作**（缺口：法人買超／財報對照需另接 `institutional_history.json`，留 v2）。

都不滿足 → `status="待驗證線索"`。

## 3. 已反映偵測（規格第 3 點、設計小抄第三節，參數照抄不另調）

以事件日（或其前最近一個交易日）為 D：
- `run_before = close(D) / close(D 前第 5 個交易日) − 1`；`> 0.15` → `reflected="caution"`
- `pre_vol_spike = max(vol(D−1), vol(D−2)) / 平均vol(D−3..D−22)`；`> 2` → 加註 `pre_volume_spike=true`（疑似提前反映）
- 兩者皆否 → `reflected="fresh"`；價格資料不足 → `reflected="unknown"`（不猜）
- `caution` 或 `pre_volume_spike` → `weight=0.5`（降權），否則 1.0

自由參數：0.15、2、5 日、20 日、±3 日——全部沿用 2026-08-23 設計小抄既有值，非本輪擬合；加上本輪新增的
「新鮮度窗 4 日」共 1 個新參數，未超過第 11 關上限 5。

## 4. 台帳寫入規則（規格第 4 點鐵律的實作）

- 只收事件日 ≥ 寫入當下台北日期 − 4 個日曆天的事件（涵蓋週末＋排程補救班次），**更舊的一律不寫**——
  防止第一次跑或停擺後恢復時把歷史事件一次補建進去。
- ID = sha1(層級|來源|代號|事件日|標題) 前 16 碼；已存在的 ID **不覆寫任何欄位**（append-only）。
- 寫入欄位：id／recorded_at／event_date／layer／source／source_id(url)／type／code／title／status／
  cross_validation／entry_close／entry_date／run_before／pre_vol_spike／reflected／weight／returns{t5,t20,t60}=null。
- 進場價＝寫入當下 `price_history.json` 最新收盤（≤寫入日），超過 10 天視為過期 → `entry_close=null`，該筆不回填。

## 5. 回填規則

`update_signal_ledger_returns.py`：以 `entry_date` 為錨，T+5/T+20/T+60 交易日（2330 日曆近似，
沿用 `update_picks_ledger_returns.py` 同一套函式）回填 `return_pct` 與 `excess_vs_taiex_pct`（yfinance `^TWII`）；
**已填欄位永不更動**。

## 6. 事前綁定的檢定假說與判準（樣本到門檻才執行）

H1：`status="訊號"` 且 `reflected="fresh"` 的 T+20 相對 TAIEX 超額報酬平均 > 0，且高於
「待驗證線索 ∪ caution」組。

- 樣本門檻（規格第 5 點）：主組 n≥30 才做初步檢定、n≥100 才可正式判定與調權重。
- 第 2 關控制組：同日、同市場別隨機抽未出訊號股票 1000 次，主組平均須 > 控制組 95 百分位。
- 第 6 關：至少跨 2 個日曆季，各季同號。
- 天條一：本條是事件訊號、非組合策略；若日後組成部位，另行計 MDD。
- 跨市場複製：美股對應物為 B18 的 SEC 8-K（#431 已 FAIL），本條只在台股登記；US 版另開。
- 多重比較：本登記計入 N 一次；H1 之外的切法（依類型／來源細分）一律算新試驗。
