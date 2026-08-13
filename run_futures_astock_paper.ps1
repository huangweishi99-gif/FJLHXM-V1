$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
$env:PYTHONUNBUFFERED = '1'

$root = 'C:\Users\Administrator\quant_futures'
$logs = Join-Path $root 'runtime\logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
Set-Location $root

. (Join-Path $root 'scripts\resolve_domestic_paper.ps1')

$python = 'C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe'
$script = Get-DomesticPaperScript -Root $root
$runLog = Join-Path $logs 'futures_astock_paper_run.log'
$errLog = Join-Path $logs 'futures_astock_paper_err.log'

& $python -u $script 1>> $runLog 2>> $errLog
