# xian.95-2: register the warrant snapshot task (AlphaWarrantSnapshot), Mon-Fri 17:30. Plain ASCII on purpose.
# Holidays are skipped inside research\warrant_snapshot_daily.py (data/trading_calendar.json).
# Re-runnable (-Force). To remove: Unregister-ScheduledTask -TaskName AlphaWarrantSnapshot -Confirm:$false
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 40)
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"C:\alpha\alpha-app\scripts\run_warrant_snapshot.ps1`""
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At "17:30"
Register-ScheduledTask -TaskName "AlphaWarrantSnapshot" -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description "Alpha warrant daily snapshot Mon-Fri 17:30 + weekly backup (research/warrant_snapshot_daily.py)" -Force | Out-Null
Write-Output "registered: AlphaWarrantSnapshot"
