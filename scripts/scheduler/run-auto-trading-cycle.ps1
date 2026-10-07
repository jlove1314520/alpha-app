# 2026-10-06 (senior directive 30): launcher for the auto rebalance scheduled
# tasks. Usage: run-auto-trading-cycle.ps1 -Task run|settle|watchdog-run|watchdog-settle
# All decisions (trading day, trigger, veto window, hard limits) live in
# research\auto_rebalance_bb90.py; this file only starts it and logs.
# Comments are ASCII on purpose (PowerShell 5.1 + UTF-8 without BOM).
param([Parameter(Mandatory=$true)][string]$Task)
$repoDir = "C:\alpha\alpha-app"
$logPath = "$repoDir\research\data\auto_trading\scheduler.log"
$pythonExe = "C:\Users\user\AppData\Local\Microsoft\WindowsApps\python.exe"
New-Item -ItemType Directory -Force -Path (Split-Path $logPath) | Out-Null
switch ($Task) {
  "run"              { $a = @("research\auto_rebalance_bb90.py","--run") }
  "settle"           { $a = @("research\auto_rebalance_bb90.py","--settle") }
  "watchdog-run"     { $a = @("research\auto_rebalance_bb90.py","--watchdog","run") }
  "watchdog-settle"  { $a = @("research\auto_rebalance_bb90.py","--watchdog","settle") }
  "preflight"        { $a = @("research\auto_rebalance_bb90.py","--preflight") }  # senior directive 34: read-only check, never places orders
  default            { exit 2 }
}
Set-Location $repoDir
$env:PYTHONUTF8 = "1"
$env:ALPHA_SCHEDULED_TASK = "1"  # senior directive 38: --live-cancel-test refuses to run under the scheduler
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$stamp = Get-Date -Format "yyyy-MM-ddTHH:mm:ss"
$out = & $pythonExe -X utf8 @a 2>&1 | Out-String
$code = $LASTEXITCODE
# senior directive 44: second line of defence - mask Taiwan national-ID-shaped strings before logging
$out = $out -replace '\b[A-Z][12][0-9]{8}\b', '<masked>'
Add-Content -Path $logPath -Value "[$stamp] task=$Task exit=$code`n$out" -Encoding UTF8
if ($Task -eq "run" -or $Task -eq "settle") {
  # best effort: publish the de-identified heartbeat; failure must never change the exit code
  $pub = & $pythonExe -X utf8 "scripts\scheduler\publish_heartbeat.py" 2>&1 | Out-String
  Add-Content -Path $logPath -Value "[$stamp] publish_heartbeat: $pub" -Encoding UTF8
}
exit $code
