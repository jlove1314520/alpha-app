# 提案：稽核 reproducibility_check 在雲端失效的修法（先.一三二-8）

2026-10-23 DevQueue 20261023-133102 寫，**未動任何程式**，等總司令裁示。

## 1. 問題（證據）

- `data/audit_report.json` `reproducibility_check`（2026-10-23 03:16 那一班）：檢查 225 支，
  IMPORT_ERROR 200、FILE_NOT_FOUND 11、OK 14。
- 200 筆 IMPORT_ERROR 的錯誤訊息**全部**是 `ModuleNotFoundError: No module named 'numpy'`（163）或
  `'pandas'`（37）——雲端 `audit.yml` 第 40 行只裝 `requests certifi urllib3`。
- 本機（有 numpy／pandas）用固定種子 20261023 從這 200 支抽 20 支重跑 import：**20／20 全部 OK**。
  所以雲端那 200 筆是「環境缺套件」，不是腳本壞掉；真的壞掉的（#23 那種 dangling import）會被淹沒在裡面看不到。
- 研究腳本用到的第三方套件（`research/*.py` 頂層 import 次數）：pandas 441、numpy 294、requests 94、
  scipy 87、yfinance 13、pyarrow 7、bs4 7、shioaji 5、sklearn 3、statsmodels 2。
- **本機也跑不完**：同一次抽樣量到每支 import 平均 2.0 秒、最慢 2.8 秒（每支開一個子行程、重新載入 pandas），
  225 支序列跑約 7.6 分鐘，超過 `scripts/audit_preflight.py` 給的 300 秒逾時——上一輪本機
  `--skip-rerun` 逾時中止就是這個原因。也就是說**目前雲端、本機兩邊都拿不到一份有效結果**。

## 2. 三個做法（照交辦列出）＋一個組合

| 做法 | 內容 | 影響 | 風險 |
|---|---|---|---|
| ① 雲端改裝套件 | `audit.yml` 安裝改成 `requests certifi urllib3 numpy pandas scipy` | 雲端能真的驗到大部分腳本 | 每晚多約 30～60 秒安裝；序列跑 225 支在雲端估 4～8 分鐘（本機實測 2.0 秒/支，雲端未量），**很可能也撞 300 秒逾時**，要搭配下面的並行；頂層有副作用的腳本（網路請求）會在雲端真的被 import——現有子行程 10 秒逾時＋net_guard 防呆照舊，風險跟本機一樣不更大 |
| ② 缺第三方套件改記 ENV_MISSING | `check_one()` 遇到 `ModuleNotFoundError` 且缺的模組不是 `research/` 裡的檔案 → 記 `ENV_MISSING`，不算 broken | 不再誤報；改一個函式 | 單獨用的話雲端只驗得到 14 支，等於這個檢查名存實亡；只解決「假警報」不解決「沒在檢查」 |
| ③ 改本機排程跑完整版 | 本機排程每天跑一次，雲端只讀結果檔 | 本機有全部套件，驗得最完整 | 多一個本機排程＝多一個會停擺的點（十一節：監控自己也要被監控）；本機關機／重開機那天就沒結果；結果檔要進 repo 才看得到 |
| **④（建議）①＋②＋並行** | ① 裝 numpy／pandas／scipy；② 剩下沒裝的少數套件（yfinance、shioaji、sklearn…）記 ENV_MISSING；`check_one()` 改用 4 條並行子行程（`ThreadPoolExecutor`），audit_preflight 逾時維持 300 秒 | 雲端驗得到約 200 支以上，真壞掉的不再被淹沒；本機也能在逾時內跑完 | 安裝時間＋約 30～60 秒；並行時同時多開 4 個 Python 子行程，雲端 runner 2 核心足夠；ENV_MISSING 的少數腳本仍驗不到，報告裡照列清單不隱藏 |

## 3. 建議與理由

建議 ④。理由：② 是必修（把「環境缺東西」誤記成「腳本壞掉」本身就是錯的分類），但只做 ② 檢查就形同虛設；
① 補上主要套件才有實質覆蓋；並行是因為本機實測序列跑已經超過逾時，不並行的話 ① 很可能只是把「缺套件」換成「逾時」。
不選 ③：多一個本機排程就多一個停擺點，雲端本來就每晚在跑。

## 4. 核准後要改的檔案（心跳）

- `.github/workflows/audit.yml`（維運帽）：安裝那一行加 `numpy pandas scipy`。
- `research/reproducibility_check.py`（不在十三節核心檔案清單內）：`check_one()` 加 ENV_MISSING 分類；`main()` 改並行；
  `by_status_count` 多一個 ENV_MISSING、不算進 broken。
- 驗收：本機跑 `python research/reproducibility_check.py --skip-rerun` 在 300 秒內完成；下一班雲端 audit 的
  `reproducibility_check.detail.by_status_count` IMPORT_ERROR 不再是 numpy／pandas。
