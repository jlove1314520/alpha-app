# senior directive 46: Telegram read-only fetch launcher (08:15 / 20:15, random delay set on the task trigger).
# Never affects trading tasks; failures are recorded by telegram_reader.py itself (exit code always 0).
$repoDir = "C:\alpha\alpha-app"
$outDir  = "C:\alpha\telegram_export\sinopac_api"
$logPath = "$outDir\_runner.log"
$pythonExe = "C:\Users\user\AppData\Local\Microsoft\WindowsApps\python.exe"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
Set-Location $repoDir
$env:PYTHONUTF8 = "1"
$env:ALPHA_SCHEDULED_TASK = "1"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$stamp = Get-Date -Format "yyyy-MM-ddTHH:mm:ss"
$out = & $pythonExe -X utf8 "research\telegram_reader.py" 2>&1 | Out-String
$out = $out -replace '\b[A-Z][12][0-9]{8}\b', '<masked>'
Add-Content -Path $logPath -Value "[$stamp] exit=$LASTEXITCODE`n$out" -Encoding UTF8
exit 0
