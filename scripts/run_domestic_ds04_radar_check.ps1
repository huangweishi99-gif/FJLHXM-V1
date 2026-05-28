$ErrorActionPreference = "Stop"
Set-Location "C:\Users\Administrator\quant_futures"
$env:PYTHONPATH = "src"
$py = "C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"
& $py -m py_compile src\fengji_total_radar.py src\fengji_pending_orders.py scripts\check_ds04_fg_sa_20260526.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $py scripts\check_ds04_fg_sa_20260526.py data
& $py src\fengji_total_radar.py --data-dir data --symbols FG,SA --out-dir runtime\fengji_radar_ds04_check --top-n 80 --daily-tail 520 --h1-tail 3200
& $py src\fengji_pending_orders.py --radar runtime\fengji_radar_ds04_check\radar.json --out-dir runtime\fengji_pending_orders_ds04_check --max-distance-pct 0.08
"--- DS04 radar check rows ---"
if (Test-Path runtime\fengji_radar_ds04_check\radar.csv) {
    Select-String -Path runtime\fengji_radar_ds04_check\radar.csv -Pattern "DS04" | ForEach-Object { $_.Line }
}
"--- DS04 pending check rows ---"
if (Test-Path runtime\fengji_pending_orders_ds04_check\pending_orders.csv) {
    Select-String -Path runtime\fengji_pending_orders_ds04_check\pending_orders.csv -Pattern "DS04" | ForEach-Object { $_.Line }
}
