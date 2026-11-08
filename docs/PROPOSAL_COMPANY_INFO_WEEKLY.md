# 提案：公司基本資料／產業別（company_info）每週自動更新（先.一三五-1nb）

2026-11-08 DevQueue 20261108-140101 撰寫。**只是提案，未改任何排程或程式。**
適用零之二「24 小時預設放行」：24 小時內沒有 Cowork 裁示，照下面「建議選項：甲」執行。

## 為什麼要做

- `data/company_info.json` 的官方產業別來自 `scripts/apply_official_industry.py`，這支一直是**手動跑**。
- 10/13 跑過一次後，到 11/08（先.一三五-1mm）才再跑，中間約 3.5 週沒更新：期間 8 檔轉上市櫃、12 家新興櫃公司都沒進名冊
  （11/08 重跑 `added_company: 12`、`changed: 12`）。
- 影響：搜尋、同產業百分位、類股資金流對新掛牌公司是空的或錯類。根因不是程式壞，是「沒人記得跑」——要交給排程。

## 請求量（照 C:\alpha\CLAUDE.md「公司基本資料／產業別」節）

一次 4 個請求：TWSE openapi `t187ap03_L` 1 次＋TPEx openapi `mopsfin_t187ap03_O`／`mopsfin_t187ap03_R`／`tpex_index_consti` 3 次。
兩家都未公布上限。每週 1 次 → 每週 4 次，遠低於現有每日管線用量（`update_stock_financials.py` 每日約 66 次）。

## 選項

### 甲（建議）：掛 `audit.yml`，每週一那班跑；腳本自己判斷「未滿 6 天就略過」

1. `audit.yml` 在「更新官方在市名冊」之後加一步：
   `python scripts/apply_official_industry.py --weekly`，`continue-on-error: true`（失敗只略過，不拖垮稽核）。
2. 腳本加 `--weekly`：讀 `meta.official_industry_2026_10_13.applied_at`，未滿 6 天就印一行「略過」、零請求、exit 0。
   這樣不用改 cron（audit.yml 週一～五 23:20 都會叫，實際每週只打一次），也不怕某一班沒觸發就整週漏掉（下一班自動補）。
3. 改接 `data/rate_limit_state.json` 共用節流：來源名 `twse_openapi`／`tpex_openapi`，同源間隔 ≥3 秒，
   402/403/428/429 記封鎖 2 小時、不重試（照 `.github/scripts/fetch_insider_transfer_tw.py` 既有的 `_rate_limit_*` 寫法，含跨行程鎖）。
4. 十節：`audit.yml` commit 步驟的 `git add` 清單加 `data/company_info.json`、`research/data/official_industry_code_map.json`、
   `data/rate_limit_state.json`（已確認三者都沒被 .gitignore 排除；目前 audit.yml 清單裡都沒有，必須補，否則又是「機器寫的檔沒進清單」）。
5. 同步改 `C:\alpha\CLAUDE.md`「公司基本資料／產業別」節：「手動跑」改成「audit.yml 每週 1 次（未滿 6 天略過），一次 4 個請求」。
6. 驗證：本機 `--weekly` 跑兩次（第一次因 11/08 剛跑過應略過、零請求）；冒煙測試；下週一雲端那班看 commit。

- 優點：雲端跑，不靠本機電腦開機；每週只多 4 次請求；自帶補跑。
- 風險：GitHub Actions 主機打 TWSE／TPEx openapi 偶爾被軟性限流（回 200 但空）——腳本已有「筆數過少就不覆蓋、exit 1」守門，
  `continue-on-error` 讓稽核照跑。company_info 約 740KB，每週改寫一次，對 repo 大小影響小。

### 乙：本機 Windows 排程每週一次

- 不改雲端，但電腦沒開就漏；新增排程要總司令本人操作（權限），所以要列「總司令待辦」。不建議。

### 丙：維持手動，只在稽核報告加「company_info 超過 14 天未更新」警示

- 零請求，但仍然靠人記得，這次的問題會再發生。不建議。

## 建議

**甲**。24 小時無裁示即照甲執行（零之二預設放行；不涉及真錢、刪除、密碼、付費資料、關卡門檻）。
