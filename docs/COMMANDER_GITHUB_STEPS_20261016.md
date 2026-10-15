# 總司令要在 GitHub 做的設定（先.一〇二-3、先.一〇三-16／18／19）

2026-10-16 互動視窗整理。**CC 不經手任何金鑰或 token**：金鑰在你自己的電腦產生、直接貼進 GitHub，CC 看不到。

> ⚠️ 下面 GitHub 網頁與手機 App 的畫面，CC 沒有親眼看過。步驟是依 GitHub 官方文件寫的，**未親自驗證，以你看到的畫面為準**。找不到某個按鈕時告訴 CC 你看到什麼，不用照著硬找。

## 一、先.一〇三-19 內部人姓名雜湊金鑰（必做；不做的話姓名雜湊會停寫，但不會外洩）

1. 在這台電腦開 PowerShell，貼上下面這一行後按 Enter。它會產生一組 32 位元組的隨機金鑰並**直接放進剪貼簿**，畫面上不會顯示，也不會存成檔案：

   ```powershell
   $b=New-Object byte[] 32; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); [Convert]::ToBase64String($b) | Set-Clipboard; "已複製到剪貼簿"
   ```

2. 瀏覽器開 <https://github.com/jlove1314520/alpha-app/settings/secrets/actions>（此為完整網址，勿修改任何字元）。
3. 依官方文件，按「New repository secret」：Name 填 `INSIDER_HASH_KEY`，Secret 欄位按 Ctrl+V 貼上，按「Add secret」。
4. 貼完後可以隨便複製別的文字蓋掉剪貼簿。
5. **這把金鑰之後不要換**：換了以後同一個人的雜湊會變，無法跟之前的紀錄對上。

驗收（CC 做）：下一次台北 05:43 美股班次後，`data/insider_transfer_tw_history.json` 的 `meta.hash_scheme` 應為 `hmac-sha256-v2`；若是 `none` 代表 Secret 沒讀到。

## 二、先.一〇三-16 User-Agent 聯絡信箱（選做）

SEC 要求程式在 User-Agent 帶聯絡方式。現在程式一律用專案佔位信箱，**不再寫死你的個人 email**。
若你想讓 SEC 有真的聯絡管道，可以另開一個專用信箱，在同一頁新增 Secret：Name `ALPHA_UA_CONTACT`，值填那個信箱。不設也能跑。

## 三、先.一〇三-18 台股主班補救觸發（不用做任何事）

查證結果：GitHub 官方文件寫明 workflow 自帶的 `GITHUB_TOKEN` 觸發 `workflow_dispatch` 時「仍會建立新的 run」
（<https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow>），
所以 **不需要你另外建立 token**，已在 workflow 加 `actions: write` 權限。

唯一可能的例外：如果 repo 設定裡「Workflow permissions」被設成唯讀且不允許提升，第一次觸發會失敗；CC 會在第一次實際觸發時看結果，失敗再請你改設定。

## 四、先.一〇二-3 手機推播（必做）

依官方文件：GitHub 手機 App → 右下「Profile」→ 右上齒輪「Settings」→「Notifications」→「Actions」，
開啟「Failed workflows only」（只推失敗的工作流程）。本機停擺時會收到「本機排程停擺告警」失敗的推播。

另外電腦版 <https://github.com/settings/notifications> 的「Actions」區也要勾選通知（官方文件說手機推播與網頁設定連動）。
