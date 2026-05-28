Set-Location "C:\Users\Administrator\quant_futures"
"--- processes ---"
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "data_manager_futures|峰极总定式01-08国内期货A股模拟实盘|fengji_radar_order_loop|fengji_futures_pending_order_monitor" } | ForEach-Object {
    "PID=$($_.ProcessId) CMD=$($_.CommandLine)"
}
"--- paper err ---"
if (Test-Path runtime\logs\paper_futures_err.log) { Get-Content runtime\logs\paper_futures_err.log -Tail 40 }
"--- radar err ---"
if (Test-Path runtime\logs\futures_radar_order_loop_err.log) { Get-Content runtime\logs\futures_radar_order_loop_err.log -Tail 40 }
"--- pending err ---"
if (Test-Path runtime\logs\futures_pending_order_monitor_err.log) { Get-Content runtime\logs\futures_pending_order_monitor_err.log -Tail 40 }
"--- paper run ---"
if (Test-Path runtime\logs\paper_futures_run.log) { Get-Content runtime\logs\paper_futures_run.log -Tail 20 }
"--- radar run ---"
if (Test-Path runtime\logs\futures_radar_order_loop.log) { Get-Content runtime\logs\futures_radar_order_loop.log -Tail 30 }
"--- pending run ---"
if (Test-Path runtime\logs\futures_pending_order_monitor.log) { Get-Content runtime\logs\futures_pending_order_monitor.log -Tail 10 }
