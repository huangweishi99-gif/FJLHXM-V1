$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
$env:PYTHONUNBUFFERED = '1'

$root = 'C:\Users\Administrator\quant_futures'
$logs = Join-Path $root 'runtime\logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
Set-Location $root

$python = 'C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe'
$runLog = Join-Path $logs 'data_manager_futures_run.log'
$errLog = Join-Path $logs 'data_manager_futures_err.log'

$cmd = "`"$python`" -u data_manager_futures.py >> `"$runLog`" 2>> `"$errLog`""
& cmd.exe /d /c $cmd
