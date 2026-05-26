$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
$env:PYTHONUNBUFFERED = '1'

$root = 'C:\Users\Administrator\quant_futures'
$logs = Join-Path $root 'runtime\logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
Set-Location $root

$python = 'C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe'
$script = Get-ChildItem -LiteralPath $root -File |
  Where-Object { $_.Name -like '*01-08*A*.py' } |
  Select-Object -First 1 -ExpandProperty FullName
if (-not $script) {
  throw 'paper script not found: *01-08*A*.py'
}
$runLog = Join-Path $logs 'futures_astock_paper_run.log'
$errLog = Join-Path $logs 'futures_astock_paper_err.log'
& $python -u $script 1>> $runLog 2>> $errLog
