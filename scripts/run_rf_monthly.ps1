# Monthly risk-free-rate export launcher (Alpha Paper-1 input). Plain ASCII on purpose (PowerShell 5.1).
#
# What it does: runs scripts\export_rf_monthly.py, which downloads the CBC open-data CSV (A13Rate.csv)
# and rewrites data\rf_monthly.json (small file, official open data). The GitHub runner only READS that
# file (research/cbc_rf_rate_client.py), so it needs no network access to CBC and no pyarrow.
# If the file changed, commits that single path (git commit -o) and pushes.
#
# Rule-10 note: this launcher rewrites exactly one tracked file, data/rf_monthly.json, and commits it
# path-scoped. No GitHub workflow rewrites that file (workflows only read it), so no workflow git-add
# allowlist entry is needed. The monthly series changes at most once a month, so no change means no commit.

$repoDir = "C:\alpha\alpha-app"
$logPath = "$repoDir\research\data\rf_monthly_cycle.log"
$outFile = "data/rf_monthly.json"
$pythonExe = "C:\Users\user\AppData\Local\Microsoft\WindowsApps\python.exe"

Set-Location $repoDir
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $logPath -Value "`n===== rf_monthly launcher: $ts =====" -Encoding utf8

$out = & $pythonExe scripts\export_rf_monthly.py 2>&1
$rc = $LASTEXITCODE
Add-Content -Path $logPath -Value ($out -join "`n") -Encoding utf8
if ($rc -ne 0) {
    Add-Content -Path $logPath -Value "export failed rc=$rc, old file kept, no commit" -Encoding utf8
    exit 0
}

# fetched_at changes every run; only commit when the monthly series itself changed.
$old = git show "HEAD:$outFile" 2>$null
$changed = $true
if ($LASTEXITCODE -eq 0 -and $old) {
    $a = (($old | Out-String) | ConvertFrom-Json).monthly | ConvertTo-Json -Compress
    $b = ((Get-Content $outFile -Raw -Encoding utf8) | ConvertFrom-Json).monthly | ConvertTo-Json -Compress
    if ($a -eq $b) { $changed = $false }
}
if (-not $changed) {
    git checkout -- $outFile 2>&1 | Out-Null
    Add-Content -Path $logPath -Value "monthly series unchanged, no commit" -Encoding utf8
    exit 0
}

git add -- $outFile 2>&1 | Out-Null
$msg = "rf_monthly monthly auto-update $ts`n`nRule-10 allowlist note: scripts/run_rf_monthly.ps1 rewrites only data/rf_monthly.json (tracked, path-scoped commit); workflows only read it, no allowlist entry needed."
git commit -o -m $msg -- $outFile 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Add-Content -Path $logPath -Value "commit failed (index lock?); will retry next run" -Encoding utf8
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
    Add-Content -Path $logPath -Value "push failed after 5 attempts, commit stays local" -Encoding utf8
}
exit 0
