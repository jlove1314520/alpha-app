# 提案：本機 AlphaData 不再改寫 App 的融資維持率檔

建立：2026-10-13（先.八十二-11a）。**只是提案，未改程式。**`alpha-data` 屬「動之前先確認」的區域（C:\alpha\CLAUDE.md），所以等總司令裁示。

## 1. 問題（有證據）

- 本機排程 **AlphaData** 每天 15:30 跑 `C:\alpha\alpha-data\run_daily.py`。其中 `compute_margin_maintenance.main()` 會把結果寫進 **`C:\alpha\alpha-app\data\margin_maintenance.json`**，也就是 App 讀的那一份。
- 這份檔案本來由雲端 market.yml 的 `.github/scripts/update_margin_maintenance.py` 每天產生，雲端版的內容比較完整：
  - 分子分母同一天（2026-10-07 先.四十三-三起）；
  - 有官方來源說明與 `generated_at`；
  - 有對齊籌碼K 的 `ratio_pct_ck`。
- 本機版的算法比較舊：分母用 FinMind 全市場融資金額，沒有 `ratio_pct_ck`、`generated_at`、來源說明。而且它是「同一天就整筆取代」。
- **2026-10-13 15:45 實際發生**：
  - 本機版把當天紀錄改寫成舊格式，冒煙 #58「維持率主數字對齊籌碼K」因此失敗（最新紀錄沒有 ratio_pct_ck）。
  - 這份改寫沒有提交，只留在本機工作區。但只要本機任何流程把 `data/` 掃進提交，或之後 `git pull` 遇到雲端也改了同一檔，就會蓋掉雲端版或造成衝突。
- 如果 App 透過本機伺服器讀到這份工作區檔，維持率主數字會短暫變成舊算法、沒有籌碼K口徑的值。

## 2. 選項

| 選項 | 做法 | 好處 | 風險 |
|---|---|---|---|
| **甲、本機改寫到 alpha-data 自己的檔（建議）** | `compute_margin_maintenance.py` 的 `OUTPUT_PATH` 改成 `alpha-data` 底下的檔（例：`alpha-data/margin_maintenance_local.json`），不再碰 alpha-app | 一行改動；雲端版成為 App 唯一來源；本機版仍保留供對照 | 動到 alpha-data 的一個常數（需裁示） |
| 乙、本機停寫 | `run_daily.py` 不再呼叫這一步 | 最乾淨 | 失去本機這份舊算法對照（目前沒有任何程式讀它） |
| 丙、只補缺不覆蓋 | 本機只在雲端那天沒有紀錄時才寫 | 雲端沒跑時還有數字 | 兩種算法混在同一份檔、口徑不一；App 顯示會跳動 |

## 3. 建議

採 **甲**。理由：
- 雲端版已經是 App 與研究共用的主來源。
- 本機舊算法留作對照即可，不該寫進 App 的檔。
- 改動只有一個路徑常數，不動 `fetch.py`、`parsers.py` 等抓取邏輯。

## 4. 不裁示的後果

每天 15:30 後本機工作區的 `data/margin_maintenance.json` 會被改成舊格式。目前靠的是「沒有程式把它提交」與「冒煙會抓到（#58）」；遇到時要手動還原（今天 15:45 那次已還原成雲端版）。
