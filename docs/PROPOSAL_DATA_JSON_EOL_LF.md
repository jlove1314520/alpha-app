# 提案：data/ 底下 JSON 本機工作目錄換行固定 LF（先.一三五-1kh-z）

> DevQueue 20261105-070102 寫，送 AWAITING。**本提案不動任何程式、不動 .gitattributes。**

## 一、現況（2026-11-05 07:0x 本機實測，指令 `git ls-files --eol data/`）

- 本機 `core.autocrlf=true`；`.gitattributes` 只對 `*.md`、`.gitattributes` 固定 `eol=lf`，`data/` 沒有規則。
- `data/` 底下有換行的追蹤檔：**index（repo 內）LF、工作目錄 CRLF 共 360 個**（`data/*.json` 頂層 84 個，原條目寫 83 個是前一輪數字）；兩邊都 LF 只有 2 個。
- **例外 1 個**：`data/auto_heartbeat.json` 在 index 內就是 CRLF（`i/crlf w/crlf`），由 `scripts/scheduler/publish_heartbeat.py` 在本機寫入後 commit。→ 加規則後 `git add --renormalize` **不是零變化**，這 1 個檔會變成一次「CRLF→LF」的 commit（內容不變）。
- 其餘大多數 JSON 是單行（`i/none w/none`，沒有換行），不受影響。

## 二、量大小的檢查是量哪一份

| 檢查 | 量的是 | 本機 vs 線上差距 |
|---|---|---|
| 冒煙 #65 `data/STATUS.json < 100 KB` | **工作目錄檔**（`fs.statSync`，`scripts/smoke_test.mjs` 約 2303 行） | 本機 100,937 bytes、HEAD 98,727 bytes（多 2,210 bytes＝每行 1 個 CR）；上限 102,400，本機只剩約 1.4KB 餘裕、線上約 3.6KB |
| 冒煙 price_history 分桶 `< 20MB` | 工作目錄檔（約 4620 行） | 12 個分桶都是 i/lf w/crlf；b0 本機 3,128,939 vs HEAD 3,107,386（多約 0.7%），離 20MB 很遠 |
| `scripts/price_history_store.py`、`build_scores_list.py` 等用 `st_size` 印大小 | 工作目錄檔（只印 log，不擋流程） | 同上，數字偏大 |
| 首頁首次載入 350KB（1kh-o） | 走 HTTP 本機伺服器，也是工作目錄檔 | 若含多行 JSON 一樣偏大 |

結論：**本機冒煙量到的是 CRLF 版，比線上大**；方向是「偏嚴」（本機比線上早亮紅），不會漏抓線上超標，但會在線上其實沒超時讓本機冒煙 FAIL、擋住 commit。#65 現在最接近（餘裕約 1.4KB）。

## 三、選項

### 甲（建議）`.gitattributes` 加 `data/**/*.json text eol=lf`
- 做法：加一行規則 → `git add --renormalize data/` → 確認 `git diff --cached --stat` 只有 `data/auto_heartbeat.json` 一檔（換行變化、內容不變）→ 本機工作目錄重新取出（`git checkout -- data/` 前要先確認沒有未 commit 的 data 變更，或等下一次排程寫檔時自然變 LF）。
- 影響：本機量到的大小＝線上大小；之後 git 不再在每次寫檔時做 LF↔CRLF 轉換（也少了 `warning: LF will be replaced by CRLF` 這類訊息）。
- 風險：①`auto_heartbeat.json` 多一個換行 commit，若本機心跳寫檔用 Python 文字模式（Windows 預設寫 CRLF），之後每次寫入工作目錄是 CRLF、git add 時轉成 LF 存入，index 一致不會再出現 CRLF；②有本機程式直接比對 bytes（例如雜湊工作目錄檔）的話，雜湊值會變一次——目前查到的 `stale_process` 雜湊只看 `.py` 原始碼，不受影響；③可還原：刪掉那一行再 renormalize。
- 不改任何冒煙門檻。

### 乙 維持換行現狀、量大小的檢查改量 `git show HEAD:` 或 HTTP
- 需要改冒煙 #65／分桶檢查程式；但冒煙在 commit **之前**跑，量 HEAD 會量到上一版、量不到這次要 commit 的版本，結構上不對；改量「讀進來後轉 LF 的 bytes 長度」可行但每個量大小處都要記得改。

### 丙 兩者都不做
- #65 本機餘裕約 1.4KB，STATUS 再長約 1.4KB 本機冒煙就會擋 commit（線上其實沒超）；與 1kh-l STATUS 瘦身提案（丙，省約 11KB）一起做的話短期不會撞到。

## 四、建議與預設放行

建議**甲**：一行設定、結構性解決（不用每個量大小的地方各自記得），只多 1 個內容不變的 commit。
照 CLAUDE.md 零之二：24 小時內無 Cowork 裁示，DevQueue 照甲執行，執行時先跑 `git add --renormalize data/` 並貼出 `--cached --stat`，若變動不只 `auto_heartbeat.json` 就停下改回 AWAITING。

## 五、執行紀錄（2026-11-06 DevQueue，[預設放行]）

- 照甲執行：`.gitattributes` 加 `data/**/*.json text eol=lf`。
- `git ls-files --eol data/`：i/crlf 1（`data/auto_heartbeat.json`）、i/lf 520、i/none 10,498；`git add --renormalize data/auto_heartbeat.json` 後 `--cached --stat` 只有這 1 檔（206+／206−），`--ignore-cr-at-eol` 比對零內容變化，符合第四節「只有 auto_heartbeat.json」的放行條件。
- `data/STATUS.json`（工作目錄乾淨）刪掉重取：本機 69,042 bytes＝`git cat-file -s HEAD:` 69,042。其餘 CRLF 工作目錄檔不強制重取（有些正被排程改寫中），等下次寫檔自然變 LF。
- Cowork 可推翻；還原＝刪掉那一行再 renormalize。
