# xian.51-3: register the daily 18:30 disposal/notice flags task (AlphaDisposalFlags). Plain ASCII on purpose.
# Re-runnable (-Force). To remove: Unregister-ScheduledTask -TaskName AlphaDisposalFlags -Confirm:$false
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 15)
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"C:\alpha\alpha-app\scripts\run_disposal_flags.ps1`""
$trigger = New-ScheduledTaskTrigger -Daily -At "18:30"
Register-ScheduledTask -TaskName "AlphaDisposalFlags" -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description "Alpha disposal/notice flags daily 18:30 (scripts/build_disposal_flags.py -> data/disposal_flags.json)" -Force | Out-Null
Write-Output "registered: AlphaDisposalFlags"
