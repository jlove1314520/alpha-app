# 先.一〇二-1（2026-10-15）：Windows Update「使用時段」改為 07:00～01:00（手動）。
# 效果：Windows 只會在 01:00～07:00 之間自動重開機，交易日 08:30～20:00 不再被更新重開打斷。
# 寫的是「設定 → Windows Update → 進階選項 → 使用時段」同一組值（HKLM\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings），
# 需要系統管理員權限（會跳 UAC）。執行前先備份原值到 C:\alpha\task_password_backup\wu_active_hours_before.txt。
# 還原：powershell -ExecutionPolicy Bypass -File C:\alpha\set-wu-active-hours.ps1 -Revert
param([switch]$Revert)
$ErrorActionPreference = "Stop"
$key = "HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings"
$dir = "C:\alpha\task_password_backup"
$out = Join-Path $dir "wu_active_hours_result.txt"
New-Item -ItemType Directory -Force $dir | Out-Null
try {
    $before = Get-ItemProperty $key
    $line = "ActiveHoursStart=$($before.ActiveHoursStart) ActiveHoursEnd=$($before.ActiveHoursEnd) SmartActiveHoursState=$($before.SmartActiveHoursState)"
    if ($Revert) {
        $b = Get-Content (Join-Path $dir "wu_active_hours_before.txt") -Raw
        if ($b -match "ActiveHoursStart=(\d+) ActiveHoursEnd=(\d+) SmartActiveHoursState=(\d*)") {
            Set-ItemProperty $key ActiveHoursStart ([int]$Matches[1]) -Type DWord
            Set-ItemProperty $key ActiveHoursEnd ([int]$Matches[2]) -Type DWord
            if ($Matches[3] -ne "") { Set-ItemProperty $key SmartActiveHoursState ([int]$Matches[3]) -Type DWord }
        }
    } else {
        if (-not (Test-Path (Join-Path $dir "wu_active_hours_before.txt"))) {
            Set-Content (Join-Path $dir "wu_active_hours_before.txt") $line -Encoding UTF8
        }
        Set-ItemProperty $key SmartActiveHoursState 0 -Type DWord   # 0＝手動（不讓 Windows 自動調整）
        Set-ItemProperty $key ActiveHoursStart 7 -Type DWord
        Set-ItemProperty $key ActiveHoursEnd 1 -Type DWord
    }
    $after = Get-ItemProperty $key
    $msg = "OK $(Get-Date -Format s) before: $line | after: ActiveHoursStart=$($after.ActiveHoursStart) ActiveHoursEnd=$($after.ActiveHoursEnd) SmartActiveHoursState=$($after.SmartActiveHoursState)"
} catch {
    $msg = "FAIL $(Get-Date -Format s) $($_.Exception.Message)"
}
Set-Content $out $msg -Encoding UTF8
Write-Host $msg
Start-Sleep 5
