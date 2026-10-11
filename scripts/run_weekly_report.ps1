# Weekly system report (chang-bei dev-26) Sunday 20:00 launcher. Plain ASCII on purpose (PowerShell 5.1).
#
# What it does: runs scripts/build_weekly_report.py, which reads local files only (audit_report, pipeline
# freshness, TRIALS_REGISTRY, paper_*.json, auto_heartbeat event codes), writes data\weekly_report.json and
# sends one Web Push summary. No external API, no orders, no mode switch. Commits that single file and pushes.
#
# Rule-10 note: this launcher rewrites exactly one tracked file, data/weekly_report.json, committed
# path-scoped (git commit -o); it is also covered by dev_queue_runner MACHINE_WRITTEN (^data/).

$repoDir = "C:\alpha\alpha-app"
$logPath = "$repoDir\research\data\weekly_report_cycle.log"
$outFile = "data/weekly_report.json"
$pythonExe = "C:\Users\user\AppData\Local\Microsoft\WindowsApps\python.exe"

Set-Location $repoDir
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $logPath -Value "`n===== weekly_report launcher: $ts =====" -Encoding utf8

$out = & $pythonExe scripts\build_weekly_report.py 2>&1
Add-Content -Path $logPath -Value ($out -join "`n") -Encoding utf8

git add -- $outFile 2>&1 | Out-Null
git diff --cached --quiet -- $outFile
if ($LASTEXITCODE -ne 1) {
    Add-Content -Path $logPath -Value "weekly report unchanged, no commit" -Encoding utf8
    exit 0
}

$msg = "Weekly system report auto-update $ts`n`nRule-10 allowlist note: this launcher (scripts/run_weekly_report.ps1) rewrites only data/weekly_report.json (tracked, path-scoped commit). Reads local files only, no orders."
git commit -o -m $msg -- $outFile 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Add-Content -Path $logPath -Value "commit failed (index lock?); will retry next week" -Encoding utf8
    exit 0
}

$pushed = $false
for ($i = 1; $i -le 5; $i++) {
    git pull --rebase --autostash --quiet 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        git rebase --abort 2>&1 | Out-Null
        Add-Content -Path $logPath -Value "pull --rebase failed (attempt $i), aborted rebase" -Encoding utf8
        Start-Sleep -Seconds 5
        continue
    }
    git push --quiet 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Add-Content -Path $logPath -Value "push succeeded (attempt $i)" -Encoding utf8
        $pushed = $true
        break
    }
    Start-Sleep -Seconds 5
}
if (-not $pushed) {
    Add-Content -Path $logPath -Value "push failed after 5 attempts, commit stays local and goes out with the next successful push" -Encoding utf8
}
exit 0
