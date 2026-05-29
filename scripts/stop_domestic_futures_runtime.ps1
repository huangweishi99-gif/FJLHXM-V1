# Stop domestic futures runtime (ASCII-only for GBK servers)
$ErrorActionPreference = "SilentlyContinue"
$patterns = "data_manager_futures\.py|fengji_radar_order_loop\.py|fengji_futures_pending_order_monitor\.py|01-08"
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match $patterns } | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force
    Write-Host ("stopped PID=" + $_.ProcessId)
}
Start-Sleep -Seconds 3
