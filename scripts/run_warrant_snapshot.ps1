# xian.95-2: warrant daily snapshot launcher (AlphaWarrantSnapshot, Mon-Fri 17:30 Taipei). Plain ASCII on purpose (PowerShell 5.1).
#
# Runs research\warrant_snapshot_daily.py: trading-day check (data/trading_calendar.json), research\warrant_snapshot.py
# (7 requests, shared rate_limit_state), weekly zip backup to C:\alpha\backups\warrant_snapshots (outside research\data),
# and data\warrant_backup_status.json for the settings page.
# Rule-10 note: the only tracked file rewritten is data/warrant_backup_status.json (path-scoped commit under git_op_lock);
# covered by dev_queue_runner MACHINE_WRITTEN (^data/). Snapshots and backups never go into the repo.

$repoDir = "C:\alpha\alpha-app"
$logPath = "$repoDir\research\data\warrant_snapshot_cycle.log"
$pythonExe = "C:\Users\user\AppData\Local\Microsoft\WindowsApps\python.exe"

Set-Location $repoDir
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $logPath -Value "`n===== warrant_snapshot launcher: $ts =====" -Encoding utf8
$out = & $pythonExe research\warrant_snapshot_daily.py 2>&1
Add-Content -Path $logPath -Value ($out -join "`n") -Encoding utf8
exit 0
