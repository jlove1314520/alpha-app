# 2026-10-06: registers 5 Task Scheduler tasks for the auto rebalance (Mon-Fri).
# The script itself decides if the day is a TWSE trading day (official calendar)
# and if a trigger condition holds; non-trading weekdays just log NOT_TRIGGERED.
# Run from an interactive PowerShell if an automated session gets Access denied.
$defs = @(
  @{N="AlphaAutoRun0905";    T="run";             At="09:05"},
  @{N="AlphaAutoRun0940";    T="run";             At="09:40"},
  @{N="AlphaAutoWatchRun";   T="watchdog-run";    At="09:55"},
  @{N="AlphaAutoSettle1340"; T="settle";          At="13:40"},
  @{N="AlphaAutoWatchSettle";T="watchdog-settle"; At="14:00"}
)
$days = "Monday","Tuesday","Wednesday","Thursday","Friday"
foreach ($d in $defs) {
  if (Get-ScheduledTask -TaskName $d.N -ErrorAction SilentlyContinue) { Write-Output "exists: $($d.N)"; continue }
  $action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "C:\alpha\run-auto-trading-hidden.vbs $($d.T)"
  $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $days -At $d.At
  $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
  $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 20)
  Register-ScheduledTask -TaskName $d.N -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description "Alpha auto rebalance ($($d.T) $($d.At)); see docs/AUTO_TRADING_SETUP.md" | Out-Null
  Write-Output "registered: $($d.N)"
}
