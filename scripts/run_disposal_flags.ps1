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
$pythonExe = "C:\Program Files\Python313\python.exe"

Set-Location $repoDir
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $logPath -Value "`n===== disposal_flags launcher: $ts =====" -Encoding utf8

$out = & $pythonExe scripts\build_disposal_flags.py 2>&1
Add-Content -Path $logPath -Value ($out -join "`n") -Encoding utf8

# chang-bei dev-28: schema guard before publish. A file that fails its schema is restored to the
# HEAD version (old copy stays published) and a Web Push alert is sent; guard self-failure is fail-open.
$g = & $pythonExe scripts\data_schema_guard.py guard --label run_disposal_flags --push $outFile 2>&1
Add-Content -Path $logPath -Value ($g -join "`n") -Encoding utf8

# xian.82-13: push an alert when a watchlist or real-money code is newly on the disposal/notice list.
# Each listing is pushed once (state in research/data, gitignored). Self-failure only logs (rule 12).
$al = & $pythonExe scripts\disposal_alert.py 2>&1
Add-Content -Path $logPath -Value ($al -join "`n") -Encoding utf8

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
    # ruling xian.103-14w: if autostash fails to re-apply, recover other jobs' uncommitted files (scripts/local_git_commit.py pull: 0=ok, 1=failed and aborted);
    # any other exit code (or python not starting) falls back to the plain pull (section 12: a guard failing must not stop the main flow)
    $pullRc = 2
    try { & $pythonExe scripts\local_git_commit.py pull 2>&1 | Out-Null; $pullRc = $LASTEXITCODE } catch { $pullRc = 2 }
    if ($pullRc -ne 0 -and $pullRc -ne 1) { git pull --rebase --autostash --quiet 2>&1 | Out-Null }
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
