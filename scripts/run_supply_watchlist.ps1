# Supply-tightness watchlist (App tab data) daily launcher. Plain ASCII on purpose (PowerShell 5.1).
#
# What it does: runs scripts\build_supply_watchlist.py (READ-ONLY on the FinMind cache; since
# 2026-10-02 [ruling xian.10-2] the only FinMind fetcher is research\finmind_warmup.py), which
# rewrites data\supply_watchlist.json only when the content changed. If it changed, commits that single file path-scoped and pushes.
# Descriptive data only: no returns, no composite score. Not evidence, not a trial.
#
# Rule-10 note: this launcher rewrites exactly one tracked file, data/supply_watchlist.json, and
# commits it path-scoped (git commit -o). The FinMind cache it fills lives under research/data/raw
# (git-ignored) and is shared read-only with paper_supply_v2; no paper_supply_v2 record or log is
# touched. This launcher makes no FinMind call at all (quota is owned by finmind_warmup.py).

$repoDir = "C:\alpha\alpha-app"
$logPath = "$repoDir\research\data\supply_watchlist_cycle.log"
$outFile = "data/supply_watchlist.json"
$pythonExe = "C:\Users\user\AppData\Local\Microsoft\WindowsApps\python.exe"

Set-Location $repoDir
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $logPath -Value "`n===== supply_watchlist launcher: $ts =====" -Encoding utf8

$out = & $pythonExe scripts\build_supply_watchlist.py 2>&1
Add-Content -Path $logPath -Value ($out -join "`n") -Encoding utf8

git add -- $outFile 2>&1 | Out-Null
git diff --cached --quiet -- $outFile
if ($LASTEXITCODE -ne 1) {
    Add-Content -Path $logPath -Value "watchlist unchanged, no commit" -Encoding utf8
    exit 0
}

$msg = "Supply watchlist daily auto-update $ts`n`nRule-10 allowlist note: this launcher (scripts/run_supply_watchlist.ps1) rewrites only data/supply_watchlist.json (tracked, path-scoped commit); its FinMind cache is under git-ignored research/data/raw. Descriptive data only."
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
