# 先.一〇二-2（2026-10-15 總司令裁示 c1）：把排程改成「不論使用者登入與否均執行」（存一次 Windows 密碼）。
#
# 為什麼：10/15 與 9/24 兩次 Windows Update 重開機後沒人登入，"只在使用者登入時執行" 的排程整天不跑；
# S4U 雖然不用密碼，但拿不到認證存放區裡的 GitHub PAT，push 全失敗。存一次密碼的工作會載入使用者設定檔，
# 可以讀認證存放區，重開機後不登入也會跑、也推得上 GitHub。
#
# 密碼安全：
#   * 密碼只在 Windows 跳出的「輸入認證」視窗由總司令本人輸入，交給工作排程器保存（Windows LSA 機密）。
#   * 本腳本不把密碼寫進任何檔案、不印出、不開 Transcript；結果檔只記工作名稱與成功／失敗。
#   * Windows 帳號若是 Microsoft 帳戶，要輸入的是 Microsoft 帳戶密碼（不是 PIN）。
#
# 安全網：
#   * 每個工作改之前先匯出原始 XML 到 C:\alpha\task_password_backup\（XML 不含密碼），-Revert 可原樣還原。
#   * 第一個工作若因密碼錯誤失敗，立即停止，不碰其他工作。
#   * 改完用暫時工作 AlphaPushProbe（同一組認證、非互動身分）做一次 git push --dry-run，驗證推得上 GitHub，跑完即移除。
#
# 用法（系統管理員 PowerShell，或由 CC 以 UAC 啟動）：
#   powershell -ExecutionPolicy Bypass -File C:\alpha\convert-tasks-to-password.ps1 -Batch 1
#   powershell -ExecutionPolicy Bypass -File C:\alpha\convert-tasks-to-password.ps1 -Batch 1 -Revert
param([int]$Batch = 1, [switch]$Revert)

$batches = @{
    1 = @("AlphaMarketCatchup", "AlphaMarketCatchupLate", "AlphaData", "AlphaQuotesFallback", "AlphaWarrantSnapshot", "AlphaDevQueue")
    # 先.一二一-1（2026-10-20）：第 2 批＝A 組資料／研究 20 支＋B 組常駐服務／盤中報價 3 支（docs/TASK_PASSWORD_BATCH2_PLAN.md 第二節）
    2 = @("AlphaB25Control", "AlphaDataAudit", "AlphaDepCheck", "AlphaDisposalFlags", "AlphaFinMindWarmup", "AlphaHypothesisQueue", "AlphaMarathon",
          "AlphaMarginCkCheck", "AlphaMoeaPitSnapshot", "AlphaNewsFallback", "AlphaNightlySix", "AlphaOrphanScan", "AlphaPaperSupplyV2", "AlphaPhoneRegression",
          "AlphaRfMonthly", "AlphaTdccHolders", "AlphaTwDataCheck", "AlphaWeeklyReport", "AlphaTelegram0815", "AlphaTelegram2015",
          "AlphaLiveServer", "AlphaShioajiQuotes", "AlphaIbkrQuotes")
    # 第 3 批＝C 組真錢自動投資 5 支，A＋B 觀察 3 個交易日正常後才跑（AlphaIbkrGateway 是視窗程式，不改）
    3 = @("AlphaAutoRun0905", "AlphaAutoRun0940", "AlphaAutoSettle1340", "AlphaAutoWatchRun", "AlphaAutoWatchSettle")
}
$dir = "C:\alpha\task_password_backup"
New-Item -ItemType Directory -Force $dir | Out-Null
$result = Join-Path $dir ("batch{0}_result.txt" -f $Batch)
$log = New-Object System.Collections.Generic.List[string]
function Say($s) { Write-Host $s; $log.Add($s) }
function Done { Set-Content $result ($log -join "`r`n") -Encoding UTF8; Write-Host ""; Write-Host "結果已寫到 $result，這個視窗 20 秒後關閉。"; Start-Sleep 20 }

$names = $batches[$Batch]
if (-not $names) { Say "FAIL 沒有第 $Batch 批的清單"; Done; exit 1 }
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { Say "FAIL 需要系統管理員權限"; Done; exit 1 }
Say ("START {0} batch={1} revert={2}" -f (Get-Date -Format s), $Batch, [bool]$Revert)

if ($Revert) {
    foreach ($n in $names) {
        $bak = Join-Path $dir "$n.orig.xml"
        if (-not (Test-Path $bak)) { Say "SKIP $n 沒有備份"; continue }
        try {
            Register-ScheduledTask -TaskName $n -Xml (Get-Content $bak -Raw) -Force | Out-Null
            Say "REVERTED $n -> $((Get-ScheduledTask $n).Principal.LogonType)"
        } catch { Say "FAIL revert $n : $($_.Exception.Message)" }
    }
    Done; exit 0
}

$user = "$env:USERDOMAIN\$env:USERNAME"
Write-Host ""
Write-Host "要改成「不論登入與否都執行」的工作（第 $Batch 批）："
$names | ForEach-Object { Write-Host "  - $_" }
Write-Host ""
Write-Host "接下來會跳出 Windows 認證視窗，請輸入 $user 的 Windows 登入密碼。"
$cred = Get-Credential -UserName $user -Message "Alpha 排程（先.一〇二-2）：輸入這台電腦 $user 的 Windows 密碼，交給工作排程器保存"
if (-not $cred) { Say "CANCELLED 未輸入密碼，什麼都沒改"; Done; exit 1 }
$pw = $cred.GetNetworkCredential().Password

$ok = 0
foreach ($n in $names) {
    try {
        $t = Get-ScheduledTask -TaskName $n -ErrorAction Stop
        $bak = Join-Path $dir "$n.orig.xml"
        if (-not (Test-Path $bak)) { Export-ScheduledTask -TaskName $n | Set-Content $bak -Encoding Unicode }
        Set-ScheduledTask -TaskName $n -User $user -Password $pw -ErrorAction Stop | Out-Null
        Say "CONVERTED $n LogonType=$((Get-ScheduledTask $n).Principal.LogonType)"
        $ok++
    } catch {
        Say "FAIL $n : $($_.Exception.Message)"
        if ($ok -eq 0) { Say "STOP 第一個工作就失敗（多半是密碼錯誤），其餘不動"; $pw = $null; Done; exit 1 }
    }
}

# 非互動身分 push 驗證（暫時工作，跑完即移除）
$probe = "AlphaPushProbe"
$probeLog = Join-Path $dir "push_probe.log"
Remove-Item $probeLog -ErrorAction SilentlyContinue
try {
    $cmd = "/c cd /d C:\alpha\alpha-app && set GCM_INTERACTIVE=never&& set GIT_TERMINAL_PROMPT=0&& (echo user=%USERNAME% session=%SESSIONNAME% & git push --dry-run origin HEAD:refs/heads/main & echo exit=!errorlevel!) > `"$probeLog`" 2>&1"
    $act = New-ScheduledTaskAction -Execute "cmd.exe" -Argument ("/v:on " + $cmd)
    Register-ScheduledTask -TaskName $probe -Action $act -User $user -Password $pw -Force | Out-Null
    Start-ScheduledTask -TaskName $probe
    $i = 0; do { Start-Sleep 3; $i++ } while ((Get-ScheduledTask $probe).State -eq "Running" -and $i -lt 40)
    $info = Get-ScheduledTaskInfo $probe
    Say ("PUSH_PROBE LastTaskResult={0} LogonType={1}" -f $info.LastTaskResult, (Get-ScheduledTask $probe).Principal.LogonType)
    if (Test-Path $probeLog) { Get-Content $probeLog | ForEach-Object { Say "  probe> $_" } }
} catch { Say "FAIL push probe: $($_.Exception.Message)" }
finally {
    Unregister-ScheduledTask -TaskName $probe -Confirm:$false -ErrorAction SilentlyContinue
    $pw = $null; $cred = $null
}
Say ("END {0} converted={1}/{2}" -f (Get-Date -Format s), $ok, $names.Count)
Done
