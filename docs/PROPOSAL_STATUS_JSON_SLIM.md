# 提案：data/STATUS.json 瘦身（先.一三五-1kh-l）

- 寫於：2026-11-04 16:1x，DevQueue 20261104-160102（維運帽）
- 狀態：**送審中**（`research/AWAITING_REVIEW.md` 一列）；本提案**不改任何門檻**（冒煙 #65 的 100KB 上限照舊）。
- 量測方式：本機 `python` 讀 `data/STATUS.json`，各頂層欄位以 `json.dumps(..., ensure_ascii=False, indent=2)` 的 UTF-8 位元組數計；
  歷史版本用 `git log -1 --before=日期 -- data/STATUS.json` 取各時間點的 commit 再 `git show` 重算。全部零外部請求。

## 1. 現況（2026-11-04 15:12 版，檔案 78,626 bytes＝76.8KB）

| 頂層欄位 | 大小 | 筆數 | App 有沒有讀 |
|---|---|---|---|
| `data_files` | 33.2KB | 130 列 | 首頁不讀（只經 `data/status_lite.json` 取 `data/fundamentals.json` 那一列） |
| `app_data_sources` | 10.3KB | 41 | 人工對照表 |
| `known_limitations` | 6.9KB | 15 條（純字串、沒有日期欄位） | App 不讀，給人看 |
| `schedule_health` | 4.9KB | 6 | 診斷用 |
| `todo` | 4.6KB | 13 | 給人看 |
| `local_schedule_heartbeat` | 3.6KB | 11 | 經 status_lite 給首頁 |
| `field_fallback_chains` | 3.1KB | 5 | |
| `rate_limit_status` | 2.3KB | 2 | |
| 其他 9 個欄位 | 合計約 2KB | | |

另外：**現檔是 CRLF 換行**（第一行 `{\r\n`），比 LF 多約 1.7KB；推測是本機 Windows 上某支腳本用文字模式寫回（`check_local_schedule_heartbeat.py` 每 30 分鐘會重寫此檔），未逐支確認。

## 2. 近 30 天成長

| 時間點（該日最後一版） | 檔案 | data_files | known_limitations | app_data_sources |
|---|---|---|---|---|
| 10-05 `ef6abc6ddb1` | 60.1KB | 18.3KB／57 列 | 4.9KB／11 | 8.2KB |
| 10-12 `09fcfee016d` | 73.8KB | 24.0KB／82 | 4.9KB／11 | 9.8KB |
| 10-19 `7ed3f62ae8e` | 82.1KB | 29.8KB／114 | 5.2KB／11 | 10.3KB |
| 10-26 `65ae495aaf3` | 84.1KB | 31.7KB／121 | 5.8KB／12 | 10.3KB |
| 11-01 `ada2cbdf403` | **87.9KB** | 33.6KB／130 | 6.4KB／13 | 10.3KB |
| 11-04 `da7264b319a` | 75.1KB | 33.2KB／130 | 6.9KB／15 | 10.3KB |

讀法：
- 30 天成長約 +15～28KB，主力是 `data_files`（+15KB，57→130 列）；`known_limitations` +2KB。
- 11-01 那版最大（磁碟上 90,059 bytes），多出來的是 `local_pipeline_health`：**本機版本 13.1KB、雲端 runner 版本只有 0.5KB**——同一欄位依「在哪台機器產生」差 12.6KB，是最容易瞬間衝破 100KB 的來源。
- 最近 16 天（10-19→11-04）兩大欄位合計約 +0.3KB／天；照這速度離 100KB 約 2 個多月，但只要本機版 `local_pipeline_health` 再寫一次（+12.6KB）＋CRLF，餘裕剩約 7KB。

## 3. 選項

### 甲：known_limitations 超過 30 天的移到 docs，STATUS 只留連結
- 15 條裡有 10 條寫於 2026-08-27～09-15（第 0、1、2、7、8 條文內有日期；第 4、5、6、9、10 條沒寫日期，以 `git log -S` 查 `generate_status_json.py` 首次出現在 08-27／08-28）。
- 移到 `docs/KNOWN_LIMITATIONS_ARCHIVE.md`，STATUS 加一個 `known_limitations_archive: "docs/KNOWN_LIMITATIONS_ARCHIVE.md"`。
- **可省約 4.4KB**（只移文內有日期的 5 條則 2.8KB）。
- 風險：低。App 不讀此欄；要改的只有 `generate_status_json.py` 的 `KNOWN_LIMITATIONS` 常數。缺點：每月要有人再搬一次，否則又會長。

### 乙：data_files 省略「預設值」欄位
- 130 列裡 87 列的 `source` 是「通用解析（讀 generated_at）」這類 4 種通用字串、98 列的 `detail` 是空字串。改成：通用解析時不寫 `source`、`detail` 空就不寫（在檔頭加一行說明「沒寫 source＝通用解析」）。
- **可省約 7.0KB**（33.2→26.3KB），而且之後每多一列，成長也少約一半。
- 風險：中低。讀 `data_files` 的程式共 5 支（`generate_status_json.py`、`scripts/build_status_lite.py`、`scripts/check_local_schedule_heartbeat.py`、`scripts/data_schema_guard.py`、`scripts/smoke_test.mjs`），目前查到的讀法只用 `path`／`generated_at`／整體是 list；實作時要逐支再確認沒有讀 `source`／`detail`，並在 `build_data_files()` 產生端改（不是在讀取端補）。

### 丙：甲＋乙都做（**建議**）
- 合計約省 11.4KB → 約 65KB（LF 換行計），餘裕回到 35KB，足以吸收本機版 `local_pipeline_health` 的 +12.6KB。
- [自行裁量] 交辦原文預標「甲（建議）」，但量出來甲只省 4.4KB、主力成長在 `data_files`，單做甲擋不住 11-01 那種瞬間膨脹，所以建議改成丙。總司令／Cowork 可推翻。

### 不建議：丁 整份改成壓縮 JSON（無縮排）
- 78.6→64KB，零資訊損失，但每次重產整份變一行，`git diff` 讀不出哪裡變了，違反「STATUS 異動要一眼可見」的用法，不建議。

### 附帶（不在甲乙丙內，另案）
1. CRLF→LF：寫檔時統一 `newline="\n"`，省約 1.7KB；需先查清是哪支在寫 CRLF。
2. 本機版 `local_pipeline_health` 13KB：明細可比照 先.六十一 異常明細的做法移到獨立檔、STATUS 只留摘要。

## 4. 若核准，要改的檔與驗收
- 改：`generate_status_json.py`（甲：常數拆分；乙：`build_data_files()` 省略預設值），新增 `docs/KNOWN_LIMITATIONS_ARCHIVE.md`。
- 驗收：重產 STATUS.json 後量大小（目標 < 70KB）；冒煙全過（#65、#180 status_lite 一致性）；`scripts/data_schema_guard.py` 照舊通過。
- 心跳：PENDING_QUEUE 該項 `- [x]`＋本檔補「實作結果」一節。

## 5. 24 小時預設放行
本提案只改維運產出檔格式、可還原（git revert 即回），不在零之二第 2 點的排除清單內；24 小時內沒有裁示，照建議選項**丙**執行並標 [預設放行]。
