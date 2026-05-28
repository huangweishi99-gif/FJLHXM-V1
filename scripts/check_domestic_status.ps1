# Run ON domestic server
$root = "C:\Users\Administrator\quant_futures"
Set-Location $root

Write-Host "=== DATA MANAGER LOG ==="
$dm = "runtime\logs\data_manager_futures.log"
if (-not (Test-Path $dm)) { $dm = "data_sync.log" }
if (Test-Path $dm) { Get-Content $dm -Tail 8 } else { Write-Host "no dm log" }

Write-Host "`n=== LC FILE ==="
Get-ChildItem data -Recurse -Filter "LC*.csv" | Select-Object FullName, LastWriteTime, Length | Format-Table -AutoSize
if (Test-Path "data\1d\LCUSDT.csv") { Get-Content "data\1d\LCUSDT.csv" -Tail 2 }

Write-Host "`n=== ACTIVE PENDING (first 10) ==="
if (Test-Path "runtime\fengji_pending_orders\pending_orders.json") {
    $po = Get-Content "runtime\fengji_pending_orders\pending_orders.json" -Raw | ConvertFrom-Json
    $active = $po | Where-Object { $_.status -in @("ACTIVE","READY_TRIGGERED") }
    Write-Host "active count: $($active.Count) / total $($po.Count)"
    $active | Select-Object -First 10 symbol, strategy_id, status, side, trigger_price, valid_until | Format-Table
    $lc = $po | Where-Object { $_.symbol -match "LC" }
    Write-Host "LC rows:"; $lc | Select-Object symbol, strategy_id, status, side, trigger_price, valid_until | Format-Table
}

Write-Host "`n=== PAPER STATE ==="
$ps = "runtime\fengji_futures\state_futures_v2.json"
if (Test-Path $ps) {
    $s = Get-Content $ps -Raw | ConvertFrom-Json
    $syms = $s.symbols.PSObject.Properties.Name
    Write-Host "symbols in paper: $($syms -join ', ')"
}
