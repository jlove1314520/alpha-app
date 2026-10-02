# Paper-2 (supply tightness v2 FORWARD paper tracker) hourly launcher.
# Plain ASCII on purpose (PowerShell 5.1 misreads non-ASCII UTF-8-without-BOM .ps1 files).
#
# What it does: runs research\paper_supply_v2.py (idempotent, degrade-only, never exits non-zero
# on its own failures), then, ONLY if the append-only log changed, commits that single file and
# pushes. Before 2026-11-16 the script writes nothing, so nothing is ever committed.
#
# Rule-10 note: the log lives under research\data\ which is git-ignored, so it is force-added
# (git add -f) and committed path-scoped (git commit -o <file>) so this never sweeps up other
# processes' staged changes. No other repo file is rewritten by this launcher.
#
# FinMind quota (ruling xian.10-2, 2026-10-02): the python script is now READ-ONLY on the FinMind
# cache (LiveSource(read_only=True), budget 0, zero FinMind calls). The only fetcher is
# research/finmind_warmup.py (Task AlphaFinMindWarmup, hard cap 450 calls per rolling hour). Prices
# come from the cache + research/adjust.py (same as the backtest); yfinance is a flagged fallback
# only. It is a no-op outside the data window.

$repoDir = "C:\alpha\alpha-app"
$logPath = "$repoDir\research\data\paper_supply_v2_cycle.log"
$dataLog = "research/data/paper_supply_v2_log.jsonl"
$pythonExe = "C:\Users\user\AppData\Local\Microsoft\WindowsApps\python.exe"

Set-Location $repoDir
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $logPath -Value "`n===== paper_supply_v2 launcher: $ts =====" -Encoding utf8

$out = & $pythonExe research\paper_supply_v2.py 2>&1
Add-Content -Path $logPath -Value ($out -join "`n") -Encoding utf8

if (-not (Test-Path "$repoDir\research\data\paper_supply_v2_log.jsonl")) {
    Add-Content -Path $logPath -Value "no log file yet, nothing to commit" -Encoding utf8
    exit 0
}

# Changed vs HEAD (or untracked): porcelain output is non-empty only if there is something to commit.
$dirty = git status --porcelain --ignored -- $dataLog 2>$null
if (-not $dirty) {
    Add-Content -Path $logPath -Value "log unchanged, no commit" -Encoding utf8
    exit 0
}

git add -f -- $dataLog 2>&1 | Out-Null
$msg = "Paper-2 supply v2 forward log auto-update $ts`n`nRule-10 allowlist note: research/data/paper_supply_v2_log.jsonl is git-ignored (research/data/) and force-added; this launcher (scripts/run_paper_supply_v2.ps1) rewrites no other tracked file. Hypothesis tracking only (#407), not evidence."
git commit -o -m $msg -- $dataLog 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Add-Content -Path $logPath -Value "commit failed (index lock or nothing to commit); will retry next hour" -Encoding utf8
    exit 0
}

$pushed = $false
for ($i = 1; $i -le 3; $i++) {
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
    Add-Content -Path $logPath -Value "push failed after 3 attempts, commit stays local and goes out with the next successful push" -Encoding utf8
}
exit 0
