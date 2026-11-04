# 提案：`data/supply_watchlist.json` 在 STATUS 的判法（先.一三五-1kh-v2）

2026-11-04 DevQueue 20261104-180102 撰寫。**本輪只寫提案、不動程式。** 送 `research/AWAITING_REVIEW.md` 等 Cowork 審。

## 一、查證（零外部請求）

- 產生者：本機排程 AlphaDataAudit 每晚 23:00 的第二個動作 `scripts/run_supply_watchlist.ps1` → `scripts/build_supply_watchlist.py`。
- `generate_status_json.py::describe_generic()` 讀 `meta.as_of`（只有日期 → 轉成當日 18:00），本機 11/04 18:1x 判 stale（`2026-11-03T18:00`，超過預設 24 小時）。
- **這個檔內容沒變就不改寫**（`build_supply_watchlist.py::same_content()`：去掉 `as_of`／`fetch` 後比對，相同就印「[略過] 內容與既有檔相同」），所以 `as_of`＝**最後一次內容變動的日期**，不是最後一次跑的日期。
  近 6 次 commit：10/01、10/02、10/03、10/17、10/18、11/03——間隔 1～16 天。
- 真正的「有在跑」證據是 `research/data/supply_watchlist_cycle.log`：10/31、11/01、11/02、11/03 每晚 23:00 都有 `===== supply_watchlist launcher` 一行。
- `data/seed/pipeline_registry.json` **沒有任何一條看這支 log**（AlphaDataAudit 那條只看第一個動作的 `research/data_audit_cycle.log`）。

結論：STATUS 用 `as_of` 判新鮮度，結構上判不準（內容兩週沒變也是正常）；同時這支的停擺目前沒人看。
跟既有 static 先例 `strategy_history.json`（「每班跑，但內容沒變不重寫」）同型。

## 二、選項

- **甲（建議）**：`supply_watchlist.json` 列進 `GENERIC_SKIP_STALE`（同 `strategy_history.json` 先例），
  **同時**在 `pipeline_registry.json` 加一條 `AlphaSupplyWatchlist`：看 `research/data/supply_watchlist_cycle.log`，
  `freshness: log_last_timestamp`、`line_filter: "supply_watchlist launcher"`、`interval_min: 1440`、`tw_trading_days_only: false`。
  - 理由：把「內容新不新」與「有沒有在跑」分開，各用對的訊號；不會因為拿掉 STATUS 的 stale 就沒人看停擺（十一節）。
  - 已確認：`pipeline_freshness.py` `_LOG_TS_RE` 認得 `2026-11-03 23:00:21` 這種格式（無時區照台北時間）。
  - 風險：低，兩處都是設定、可還原。
- **乙**：`STALE_HOURS` 給 30 小時（原條目寫的做法）。缺點：內容兩週沒變時照樣天天亮 stale，只是把假警報從每天 5 小時變成「內容沒變的每一天」。不建議。
- **丙**：產生端每次都寫 `meta.generated_at`。缺點：檔案每晚都變、每晚多一個 commit（約 0.3MB 的 JSON 每天進 git 歷史），違背「內容沒變不改寫」的原設計。不建議。

## 三、照零之二

24 小時內（2026-11-05 18:3x 前）沒有 Cowork 裁示 → DevQueue 照**甲**執行，條目與 PROGRESS 標 [預設放行]。
