# xian.95-2: warrant daily snapshot launcher (AlphaWarrantSnapshot, Mon-Fri 17:30 Taipei). Plain ASCII on purpose (PowerShell 5.1).
#
# Runs research\warrant_snapshot_daily.py: trading-day check (data/trading_calendar.json), research\warrant_snapshot.py
# (7 requests, shared rate_limit_state), weekly zip backup to C:\alpha\backups\warrant_snapshots (outside research\data),
# and data\warrant_backup_status.json for the settings page.
# Rule-10 note: the only tracked file rewritten is data/warrant_backup_status.json (path-scoped commit under git_op_lock);
# covered by dev_queue_runner MACHINE_WRITTEN (^data/). Snapshots and backups never go into the repo.
# xian.132-5a (2026-10-23): after the snapshot it also runs research\paper_12_warrant_wave_tracker.py (paper L, trial #466,
# reads local snapshots only, zero extra requests) and commits data/paper_12.json + research/data/paper_12_log.jsonl (add -f)
# in the same path-scoped commit; covered by MACHINE_WRITTEN (^data/ and ^research/data/*.jsonl).
# Inbox 029 (xian.135-1ae-a, decided 2026-10-28): the task also gets a 20:30 trigger as a same-evening retry.
# If today's research\data\warrant_snapshots\<today>\meta.json already exists and is not partial, this launcher logs
# "already complete" and skips the python step (zero requests). A partial or missing snapshot runs the normal daily
# script, which only re-fetches the failed sources. Either way it then runs research\forward_source_gap_watch.py
# (zero requests, reads local file names / date fields only, writes research\data\forward_source_gap_watch.json).

$repoDir = "C:\alpha\alpha-app"
$logPath = "$repoDir\research\data\warrant_snapshot_cycle.log"
# xian.102-2a: the Store-app alias (WindowsApps\python.exe) printed nothing when this task ran as
# "run whether user is logged on or not" (2 runs, 10/15 22:40 and 22:44). Use the regular install, same as run-market-catchup.ps1.
$pythonExe = "C:\Program Files\Python313\python.exe"

Set-Location $repoDir
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $logPath -Value "`n===== warrant_snapshot launcher: $ts =====" -Encoding utf8
$today = Get-Date -Format "yyyy-MM-dd"
$metaPath = "$repoDiresearch\data\warrant_snapshots\$today\meta.json"
$complete = $false
if (Test-Path $metaPath) {
    try { $complete = -not ((Get-Content -Raw -Encoding UTF8 $metaPath | ConvertFrom-Json).partial) }
    catch { Add-Content -Path $logPath -Value "WARN: meta.json unreadable, running daily script: $($_.Exception.Message)" -Encoding utf8 }
}
if ($complete) {
    Add-Content -Path $logPath -Value "$today snapshot already complete, skip (zero requests)" -Encoding utf8
} else {
    $out = & $pythonExe research\warrant_snapshot_daily.py 2>&1
    Add-Content -Path $logPath -Value ($out -join "`n") -Encoding utf8
    if (-not $out) { Add-Content -Path $logPath -Value "WARN: python produced no output (exit=$LASTEXITCODE)" -Encoding utf8 }
}
try {
    $gap = & $pythonExe research\forward_source_gap_watch.py 2>&1
    Add-Content -Path $logPath -Value ("[gap watch exit=$LASTEXITCODE] " + (($gap | Select-Object -Last 3) -join " | ")) -Encoding utf8
} catch {
    Add-Content -Path $logPath -Value "WARN: gap watch failed: $($_.Exception.Message)" -Encoding utf8
}
exit 0
