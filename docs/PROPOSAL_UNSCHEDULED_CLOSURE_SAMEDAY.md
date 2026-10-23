# 提案：交易日曆當天就知道「颱風臨時休市」（先.一三二-10）

2026-10-23 DevQueue 20261023-133102 寫，**未動任何程式**，等總司令裁示。

## 1. 發生了什麼（證據）

- 2026-10-23（週五）薔琵颱風臨時休市（`data/news.json`「休市一天」「股匯期休市四天」「下周二開盤」；
  `data/events.json` 多則「原定 10/23 法說會因颱風延期」）。
- 雲端官方報價 `data/quotes_tw.json`（10/23 13:45 抓）232 檔 `date` 全是 20261022——官方資料其實當天就「看得出來沒開盤」。
- 但 `data/trading_calendar.json` 的 `tw.2026.closed`／`unscheduled_closed` 都沒有 10/23，結果：
  - `data/STATUS.json` schedule_health 把「台股逐筆tick（本機Shioaji）」判逾期，DevQueue 花一輪半查因（先.一三二-9）；
  - Shioaji 常駐行程照常登入、整天空跑，收盤 commit 了空快照（另案 先.一三二-11）；
  - 讀日曆的其他程式（`quotes_local_fallback.py`、`watchdog_dispatch_market.py`、`market_local_catchup.py`、
    `check_tw_data_landed.py`、`build_listed_universe.py`、`backfill_price_history_gaps.py`）同樣把今天當交易日。
- 現行機制（`.github/scripts/fetch_trading_calendar.py`）：`unscheduled_closed` 由 TWSE FMTQIK（市場成交資訊）
  回填，只看「今天以前」的日子，而且整份日曆「同年度 7 天內抓過就不再問」——**當天臨時休市結構上不可能當天被記到**，
  最慢要到一週後。

## 2. 做法

| 做法 | 內容 | 外部請求 | 風險 |
|---|---|---|---|
| 甲 | FMTQIK 當月那一次改成每天收盤後都問（不受 7 天快取限制），當天 14:00 以後的班次就把今天納入判斷 | 每天多 1 次 FMTQIK（官方未公布上限；現有節流 ≥3 秒、402/403/428/429 封鎖 2 小時照舊） | 盤中仍不知道；只解決「事後一週才記」 |
| 乙 | 零請求：盤中 09:30 後，若 `quotes_tw.json` 官方資料的 `date` 全部仍是前一個交易日 → 日曆另記 `suspected_closed_today`（附 source＝quotes_tw 資料日期），讀日曆的程式把它當休市 | 0（用現有報價檔） | 官方資料源本身當機也會被誤判成休市 → 所以分開欄位、只用來「暫停告警／暫停空跑」，不寫進正式 `unscheduled_closed` |
| **丙（建議）乙＋甲** | 盤中用乙先暫停誤報，收盤後用甲的 FMTQIK 正式確認並寫進 `unscheduled_closed`；兩者不一致（乙說休市、FMTQIK 有成交）時記告警 | 每天 +1 次 | 讀日曆的程式要逐一加讀 `suspected_closed_today`（約 7 支），分批改 |

## 3. 建議與理由

建議丙。乙讓盤中立刻止血（零請求），甲讓正式日曆有官方依據；只做乙會把「資料源當機」誤當休市，只做甲盤中照樣誤報。
颱風假台灣每年都有，這不是一次性的事。

## 4. 核准後要改的檔案（心跳）

- `.github/scripts/fetch_trading_calendar.py`：FMTQIK 當月每天問、`d <= today`（收盤後）。
- 新增零請求判斷（建議放在 `scripts/quotes_local_fallback.py` 或 `market.yml` 報價步驟之後的一支小腳本），寫 `suspected_closed_today`。
- 讀日曆的 7 支程式加讀新欄位；`market.yml` git add 清單照十節確認。
- 驗收：用 2026-10-23 的 `quotes_tw.json`（git 歷史版）重放，判出 10/23 為疑似休市；10/22 不誤判。
