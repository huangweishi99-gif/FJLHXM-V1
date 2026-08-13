# Remote verify: domestic pending monitor + ds03 module
$procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*fengji_futures_pending_order_monitor.py*' }
Write-Output "pending_count=$($procs.Count)"
foreach ($p in $procs) {
    Write-Output "pid=$($p.ProcessId)"
}

Set-Location "C:\Users\Administrator\quant_futures"
$env:FENGJI_MARKET = "futures"
$env:PYTHONPATH = "src;packages\fengji_core"
python -c "from fengji_core.ds03_pending_fill import resolve_ds03_pending_fill; print('ds03_pending_fill_import=ok')"
