# MOEA open-data daily PIT snapshot launcher (ruling xian.10-5.6, 2026-10-02). Plain ASCII on purpose (PowerShell 5.1).
#
# What it does: runs scripts\snapshot_moea_pit.py (stores a CSV only when its SHA256 changed; never exits
# non-zero on its own failures), then, ONLY if data\moea_pit changed, commits that directory path-scoped
# (git commit -o) and pushes. Snapshot only: no trial is registered and no return is computed.
#
# Rule-10 note: this is a local Task Scheduler task, not a workflow. It writes only new files under
# data\moea_pit\ (new snapshot files plus an appended manifest.jsonl) and the git-ignored
# research\data\moea_pit_status.json. No workflow reads or rewrites these files, so no allowlist entry is needed.

$repoDir = "C:\alpha\alpha-app"
$logPath = "$repoDir\research\data\moea_pit_cycle.log"
$pythonExe = "C:\Users\user\AppData\Local\Microsoft\WindowsApps\python.exe"
$dir = "data/moea_pit"

Set-Location $repoDir
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $logPath -Value "`n===== moea_pit launcher: $ts =====" -Encoding utf8
$out = & $pythonExe scripts\snapshot_moea_pit.py 2>&1
Add-Content -Path $logPath -Value ($out -join "`n") -Encoding utf8

$dirty = git status --porcelain -- $dir 2>$null
if (-not $dirty) {
    Add-Content -Path $logPath -Value "no new snapshot, no commit" -Encoding utf8
    exit 0
}

git add -- $dir 2>&1 | Out-Null
$msg = "MOEA open-data PIT snapshot $ts`n`nRule-10 allowlist note: local scheduled task only (not a workflow); writes new files under data/moea_pit/ and appends manifest.jsonl, nothing else tracked. Snapshot only, no trial, no returns (xian.10-5.6)."
git commit -o -m $msg -- $dir 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Add-Content -Path $logPath -Value "commit failed (index lock or nothing to commit); will retry next run" -Encoding utf8
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
