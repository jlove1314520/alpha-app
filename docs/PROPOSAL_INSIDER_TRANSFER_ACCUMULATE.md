# 提案：內部人持股轉讓事前申報「前向累積」接排程（先.九十四-5d）

> ⚠️ 狀態已更新：**2026-10-14 先.九十五-3 總司令核准**——放 market.yml 05:43 班、每日 2 請求；commit 清單已加 `data/insider_transfer_tw_history.json`；姓名與受讓人改雜湊（`name_hash`／`transferee_hash`），只留職稱與身分類別。下面是核准前的提案原文，保留供稽核。
>
> 狀態：**等總司令審閱**。本條只寫好抓取腳本與自測，**沒有改任何 workflow、沒有寫出資料檔**。
> 撰寫：DevQueue cycle 20261014-180102，2026-10-14 台北 18:1x。

## 1. 為什麼要做

`research/DATA_GAP_PLAN.md` 2.10「#41 內部人持股轉讓」：歷史只能在 mopsov 查，而 mopsov 的 robots.txt 全站禁止，**歷史不抓**。官方 openapi 有「每日事前申報表」，但**只有當天快照、不能帶日期**——今天不存，明天就沒了。所以唯一合規的做法是：從現在起每天存一份，往前累積。累積 1～2 年後才可能拿來做研究（之前不會有任何回測）。

## 2. 已經做好的東西

| 檔案 | 內容 |
|---|---|
| `.github/scripts/fetch_insider_transfer_tw.py` | 每次執行打 2 個請求（上市、上櫃各 1 次），去重後併入 `data/insider_transfer_tw_history.json`；支援 `--dry-run`（抓但不寫檔） |
| `scripts/selftest_insider_transfer_tw.py` | 不連網自測 18 項（民國轉西元、兩邊欄位統一、缺欄位警告、拒收非 JSON 陣列、去重、既有紀錄保留） |

端點（2026-10-14 18:0x 台北 curl 實測）：

| 市場 | 端點 | 實測筆數 | 日期欄 |
|---|---|---|---|
| 上市 | `https://openapi.twse.com.tw/v1/opendata/t187ap12_L` | 3 | 出表日期 1151013 |
| 上櫃 | `https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap12_O` | 20 | Date 1151013 |

兩邊有 4 個欄位名稱不同（日期、代號、公司名、「申報人身分」vs「申請人身分」），腳本統一成同一組英文鍵，**只改名不改值**。

頻率：兩家 swagger 都沒有公布次數上限。腳本共用 `data/rate_limit_state.json`（來源名 `twse_openapi`／`tpex_openapi`，同源間隔 ≥3 秒，402/403/428/429 封鎖 2 小時不重試）。

## 3. 要總司令決定的三件事

### 決定一：放哪個排程、跑幾次

**建議：放進 `market.yml`，緊接在「借券賣出累積」那一步後面，`continue-on-error: true`，但只在 05:43 那一班跑**（每天 2 個請求）。

理由：10/14 18:0x 抓到的快照「出表日期」還是 10/13，代表當天的表不是傍晚就出來；隔天清晨那一班比較可能抓到前一天的完整表。腳本有去重，跑 3 班也不會重複記，但會變成每天 6 個請求，跟原交辦「各 1 次／日」不符。

⚠️ **未驗證**：官方幾點換新表我沒有量過。建議上線後頭兩週看 `meta.report_dates` 有沒有缺日；有缺日就改成 3 班都跑（多 4 個請求／日，仍遠低於其他 openapi 用量）。

做法（要改的那一步，**本條未改**）：
```yaml
      - name: 累積內部人持股轉讓事前申報（TWSE t187ap12_L＋TPEx mopsfin_t187ap12_O，各1次，先.九十四-5d）
        if: github.event.schedule == '43 21 * * 1-5' || github.event_name == 'workflow_dispatch'
        run: python .github/scripts/fetch_insider_transfer_tw.py
        continue-on-error: true
```

### 決定二：commit 清單要加哪個檔（CLAUDE.md 第十節）

- `market.yml` 最後的 `git add -A ...` 清單要加 **`data/insider_transfer_tw_history.json`**（它是逐檔列名，不加就會變成「工作目錄永遠髒」，重踩 2026-09-16 停擺 31 小時那次）。
- `data/rate_limit_state.json` 已經在清單裡，不用加。
- 本機 DevQueue 的 `scripts/dev_queue_runner.py::MACHINE_WRITTEN` 已用 `^data/` 涵蓋，不用改。

### 決定三：要不要保留「姓名」「受讓人」原文

官方表裡有申報人姓名和受讓人（例如家人、信託專戶）。這是公開申報內容，跟 MOPS 網頁一樣；但本 repo 是公開的，存下來等於多一份可搜尋的副本。

**建議（[自行裁量]，目前腳本的做法）：保留原文**——去重需要、日後研究要分辨「同一人多次申報」、而且是官方公開資料。若總司令不想在公開 repo 留姓名，改法很簡單：寫檔前把這兩欄換成雜湊（仍可去重與辨識同一人），不影響其他欄位。

## 4. 大小估計

實測一天 23 筆，每筆約 600 位元組（壓縮 JSON），一年約 250 個交易日 → **約 3～4 MB／年**，不設上限。若日後太大，再改成每年一個檔。

## 5. 風險與限制

- 這是「事前申報」（打算轉讓），**不是實際成交**；實際轉讓結果另有申報，本條不處理。
- 哪天排程沒跑、或兩邊都失敗，那天就**永久缺一天**（歷史只有 mopsov 有，不抓）。`meta.report_dates` 看得出缺哪天。
- 自身失敗只影響自己（`continue-on-error`），兩邊都失敗時不覆蓋既有檔；既有檔讀不回來時直接不寫，避免把累積的歷史蓋掉。
- 這是資料累積，**不是 alpha 試驗**，不登記 trial_registry、不計入 N。

## 6. 核准後要做的事（一次做完）

1. 改 `market.yml`：加上面那一步＋commit 清單加檔名（commit 訊息註明「已確認在 allowlist」）。
2. 手動觸發一次 `workflow_dispatch`，確認檔案落地、筆數與 `--dry-run` 一致。
3. 兩週後檢查 `meta.report_dates` 有無缺日，決定要不要改成 3 班都跑。
