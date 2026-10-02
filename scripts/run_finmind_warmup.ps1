# FinMind single warm-up fetcher launcher (ruling xian.10-2, 2026-10-02). Plain ASCII on purpose (PowerShell 5.1).
#
# What it does: runs research\finmind_warmup.py once (max ~14 minutes, hard cap 450 FinMind calls per
# rolling hour counted in the shared data/rate_limit_state.json). Task Scheduler runs it every 15
# minutes with MultipleInstances=IgnoreNew. It is the ONLY FinMind fetcher for paper_supply_v2 and
# build_supply_watchlist (both are read-only on the cache).
#
# Rule-10 note: this launcher commits and pushes NOTHING. It rewrites only git-ignored files under
# research\data\ (raw FinMind cache, finmind_warmup_state.json, finmind_warmup_status.json, lock) plus
# the already-shared data\rate_limit_state.json, which the existing FinMind client writes in every
# process (not a new rewrite; it is not touched by any workflow git add).

$repoDir = "C:\alpha\alpha-app"
$logPath = "$repoDir\research\data\finmind_warmup_cycle.log"
$pythonExe = "C:\Users\user\AppData\Local\Microsoft\WindowsApps\python.exe"

Set-Location $repoDir
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

if ((Test-Path $logPath) -and ((Get-Item $logPath).Length -gt 2000000)) {
    Move-Item -Force $logPath "$logPath.old"
}
$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $logPath -Value "`n===== finmind_warmup launcher: $ts =====" -Encoding utf8
$out = & $pythonExe research\finmind_warmup.py 2>&1
Add-Content -Path $logPath -Value ($out -join "`n") -Encoding utf8
exit 0
