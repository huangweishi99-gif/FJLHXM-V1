$procs = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "fengji_futures_pending_order_monitor" })
if ($procs.Count -le 1) {
    Write-Host "single pending monitor OK"
    exit 0
}
$keep = $procs | Sort-Object CreationDate | Select-Object -Last 1
foreach ($p in $procs) {
    if ($p.ProcessId -eq $keep.ProcessId) { continue }
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Host "stopped duplicate PID=$($p.ProcessId)"
}
Write-Host "kept PID=$($keep.ProcessId)"
