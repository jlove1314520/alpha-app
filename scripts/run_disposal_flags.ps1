# Disposal/notice flags (xian.51-3) daily 18:30 launcher. Plain ASCII on purpose (PowerShell 5.1).
#
# What it does: runs scripts\build_disposal_flags.py, which logs in to Shioaji (read-only market data,
# no orders) and calls api.punish() / api.notice() once each, cross-fills OTC from TPEx OpenAPI when
# Shioaji OTC data lags TSE by >1 trading day, falls back to TWSE/TPEx OpenAPI if Shioaji fails, and
# rewrites data\disposal_flags.json only when content changed. If it changed, commits that single file
# path-scoped and pushes.
#
# Rule-10 note: this launcher rewrites exactly one tracked file, data/disposal_flags.json, committed
# path-scoped (git commit -o); it is also covered by dev_queue_runner MACHINE_WRITTEN (^data/).

$repoDir = "C:\alpha\alpha-app"
$logPath = "$repoDir\research\data\disposal_flags_cycle.log"
$outFile = "data/disposal_flags.json"
$pythonExe = "C:\Users\user\AppData\Local\Microsoft\WindowsApps\python.exe"

Set-Location $repoDir
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $logPath -Value "`n===== disposal_flags launcher: $ts =====" -Encoding utf8

$out = & $pythonExe scripts\build_disposal_flags.py 2>&1
Add-Content -Path $logPath -Value ($out -join "`n") -Encoding utf8

git add -- $outFile 2>&1 | Out-Null
git diff --cached --quiet -- $outFile
if ($LASTEXITCODE -ne 1) {
    Add-Content -Path $logPath -Value "disposal flags unchanged, no commit" -Encoding utf8
    exit 0
}

$msg = "Disposal/notice flags daily auto-update $ts`n`nRule-10 allowlist note: this launcher (scripts/run_disposal_flags.ps1) rewrites only data/disposal_flags.json (tracked, path-scoped commit). Read-only market data."
git commit -o -m $msg -- $outFile 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Add-Content -Path $logPath -Value "commit failed (index lock?); will retry next day" -Encoding utf8
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
