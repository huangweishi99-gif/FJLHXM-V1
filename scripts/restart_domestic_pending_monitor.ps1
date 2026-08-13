param(
    [string]$Root = "C:\Users\Administrator\quant_futures"
)

$ErrorActionPreference = "Stop"
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*fengji_futures_pending_order_monitor.py*' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Start-Sleep -Seconds 2
& (Join-Path $Root "scripts\watchdog_domestic.ps1") | Select-Object -Last 8

Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*fengji_futures_pending_order_monitor.py*' } |
    Select-Object ProcessId, @{ N = 'cmd'; E = { $_.CommandLine.Substring(0, [Math]::Min(140, $_.CommandLine.Length)) } }
