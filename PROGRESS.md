# Alpha App — 進度紀錄

給協作用（包含另一個 Claude「Cowork」）看的進度紀錄。最新的寫在最上面，條列簡潔，讓沒看過對話的人也能接手。

---

## 2026-08-22 00:33 — 交接、建立開發環境、寫專案說明文件

**改了什麼：**
- 從 GitHub clone `jlove1314520/alpha-app` 到本機 `C:\alpha\alpha-app\`，之後開發改在本機直接進行，不再手動下載上傳。
- 檢查 repo 內容：index.html、manifest.webmanifest、sw.js、icon192.png、icon512.png，確認沒有多餘的重複舊檔（如 `index (1).html`）需要清除。
- 確認本機 Git Credential Manager 已設定好，push 時會走瀏覽器登入，不需額外設定。
- 在使用者桌面建立捷徑「Alpha」（`C:\Users\user\Desktop\Alpha.lnk`），雙擊會開 PowerShell、cd 進 `C:\alpha`、自動啟動 `claude`。對應腳本 `C:\alpha\start-alpha.bat`。
- 新增 `C:\alpha\CLAUDE.md`，整理專案結構、功能現況、關鍵決策、已知地雷（給任何接手這個 repo 的人快速上手用）。

**為什麼：**
使用者原本是手動下載 index.html 改完再上傳到 GitHub，效率差也容易漏東西。改成在本機用 Claude Code 直接開發、直接 git commit+push，取代舊流程。

**影響到哪些檔案：**
- 新增：`C:\alpha\CLAUDE.md`（不在此 repo 內，在上層目錄）
- 新增：`C:\alpha\start-alpha.bat`（不在此 repo 內）
- 新增：本檔案 `PROGRESS.md`
- 沒有修改 `alpha-app` 內任何既有檔案（index.html 等維持原樣）
- 沒有動到 `C:\alpha\alpha-data\alpha.db` 或任何 Python 資料管線檔案

**下一步：**
等使用者指示要接哪個功能。候選方向：
1. 市場頁類股/大盤真實資料
2. 美股報價（FinMind `USStockPrice`）
3. AI 盤前日報接真實新聞
4. Phase 2 券商下單研究（Shioaji / IBKR）

**卡住的問題：**
無。

---

## 專案背景（不常變動，供快速定位）

- 手機 PWA：本 repo，單一自包含 `index.html`，client-side 直接打 FinMind 免 token API。線上網址 https://jlove1314520.github.io/alpha-app/ ，push 後 GitHub Pages 約 1–2 分鐘自動部署。
- Python 資料管線（不在本 repo，在 `C:\alpha\alpha-data\`，未來 Phase 2 自動下單用）：`alpha.db` 絕不可刪除或覆蓋；`fetch.py`/`parsers.py`/`config.py` 的資料源邏輯是踩過坑調好的，不要順手重構。
- 完整背景/決策紀錄/已知地雷見 `C:\alpha\CLAUDE.md`（不在本 repo，在上層目錄，因為要涵蓋 alpha-data 部分）。
