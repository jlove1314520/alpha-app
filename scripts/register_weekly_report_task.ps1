# chang-bei dev-26: register the weekly Sunday 20:00 system report task (AlphaWeeklyReport). Plain ASCII on purpose.
# Re-runnable (-Force). To remove: Unregister-ScheduledTask -TaskName AlphaWeeklyReport -Confirm:$false
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 15)
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"C:\alpha\alpha-app\scripts\run_weekly_report.ps1`""
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At "20:00"
Register-ScheduledTask -TaskName "AlphaWeeklyReport" -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description "Alpha weekly system report Sunday 20:00 (scripts/build_weekly_report.py -> data/weekly_report.json + Web Push)" -Force | Out-Null
Write-Output "registered: AlphaWeeklyReport"
