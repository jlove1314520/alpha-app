# Paper-9 (model I, 252-day high breakout, trial #463) local scheduled launcher (Task AlphaPaper9, Mon-Fri 18:30).
# Plain ASCII on purpose (PowerShell 5.1 misreads non-ASCII UTF-8-without-BOM .ps1 files).
# Runs scripts\run_paper_9.py: tracker step() (NOT_STARTED before 2026-11-02, no ledger write), then commits only
# data/paper_9.json and research/data/paper_9_log.jsonl via scripts/local_git_commit.py commit_paths (path-scoped, git_op_lock).
# Zero external requests. Never exits non-zero on its own failures (section 12).

$repoDir = "C:\alpha\alpha-app"
$logPath = "$repoDir\research\data\paper_9_cycle.log"
$pythonExe = "C:\Program Files\Python313\python.exe"

Set-Location $repoDir
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $logPath -Value "`n===== paper_9 launcher: $ts =====" -Encoding utf8
try {
    $out = & $pythonExe scripts\run_paper_9.py 2>&1
    Add-Content -Path $logPath -Value ($out -join "`n") -Encoding utf8
} catch {
    Add-Content -Path $logPath -Value ("launcher error: " + $_.Exception.Message) -Encoding utf8
}
exit 0
