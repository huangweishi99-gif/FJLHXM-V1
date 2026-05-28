$ErrorActionPreference = "Stop"
$root = "C:\Users\Administrator\quant_futures"
$py = "C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"
Set-Location $root
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "data_manager_futures" } | ForEach-Object {
    try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop } catch {}
}
Start-Sleep -Seconds 2
$cmd = "cmd.exe /d /c cd /d `"$root`" && `"$py`" -u data_manager_futures.py >> runtime\logs\data_manager_futures.log 2>> runtime\logs\data_manager_futures_err.log"
Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd; CurrentDirectory = $root } | Out-Null
Start-Sleep -Seconds 3
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "data_manager_futures" } | ForEach-Object { "data_manager PID=$($_.ProcessId)" }
