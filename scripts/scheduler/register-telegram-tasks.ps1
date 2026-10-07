# senior directive 46: register Telegram read-only fetch tasks (daily 08:15 and 20:15, random delay 0-10 min).
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 20)
$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "C:\alpha\run-telegram-reader-hidden.vbs"
foreach ($d in @(@{N="AlphaTelegram0815"; At="08:15"}, @{N="AlphaTelegram2015"; At="20:15"})) {
  $trigger = New-ScheduledTaskTrigger -Daily -At $d.At -RandomDelay (New-TimeSpan -Minutes 10)
  Register-ScheduledTask -TaskName $d.N -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description "Alpha Telegram read-only fetch ($($d.At) +0-10min); see research/telegram_reader.py" -Force | Out-Null
  Write-Output "registered: $($d.N)"
}
