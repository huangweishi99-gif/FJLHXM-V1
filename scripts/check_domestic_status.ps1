# Run ON domestic server
$root = "C:\Users\Administrator\quant_futures"
Set-Location $root
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "=== DATA MANAGER PROCS ==="
function Get-DmProcs {
    @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -and ($_.CommandLine -match "data_manager_futures\.py")
    })
}
function Get-DmPythonProcs {
    @(Get-DmProcs | Where-Object { $_.Name -match "python" })
}
$dmProcs = @(Get-DmProcs)
$dmPy = @(Get-DmPythonProcs)
$hbPath = Join-Path $root "runtime\logs\data_manager_heartbeat.txt"
$hbAge = $null
if (Test-Path $hbPath) { $hbAge = [int](((Get-Date) - (Get-Item $hbPath).LastWriteTime).TotalSeconds) }
Write-Host "count: $($dmPy.Count) python (expect 1) wrappers=$($dmProcs.Count - $dmPy.Count) heartbeat_age_sec=$hbAge (expect <120)"
if ($dmPy.Count -gt 1) { Write-Host "WARN duplicate python — run scripts\ensure_single_data_manager.ps1" -ForegroundColor Yellow }
if ($dmPy.Count -eq 1) {
    $codePath = Join-Path $root "data_manager_futures.py"
    if (Test-Path -LiteralPath $codePath) {
        $codeMtime = (Get-Item -LiteralPath $codePath).LastWriteTime
        if ($codeMtime -gt $dmPy[0].CreationDate) {
            Write-Host "WARN code newer than PID=$($dmPy[0].ProcessId) — run ensure_single_data_manager.ps1" -ForegroundColor Yellow
        }
    }
}
if ($null -ne $hbAge -and $hbAge -gt 120) { Write-Host "WARN heartbeat stale" -ForegroundColor Yellow }
$dmPy | ForEach-Object { "PID=$($_.ProcessId) started=$($_.CreationDate)" }

$dmLog = Join-Path $root "runtime\logs\data_manager_futures.log"
if (-not (Test-Path $dmLog)) { $dmLog = Join-Path $root "data_sync.log" }
if (Test-Path $dmLog) {
    $idleLine = Get-Content $dmLog -Tail 30 -Encoding UTF8 | Where-Object { $_ -match "不在数据更新时段" } | Select-Object -Last 1
    if ($idleLine) {
        Write-Host "next_window: $idleLine"
    }
    $pgLine = Get-Content $dmLog -Tail 800 -Encoding UTF8 | Where-Object { $_ -match "\[PG\]|pg2608" } | Select-Object -Last 1
    $scLine = Get-Content $dmLog -Tail 800 -Encoding UTF8 | Where-Object { $_ -match "\[SC\]|sc2608" } | Select-Object -Last 1
    if ($pgLine) { Write-Host "log_pg: $pgLine" }
    if ($scLine) { Write-Host "log_sc: $scLine" }
}

Write-Host "`n=== 15m FRESHNESS (newest 3) ==="
Get-ChildItem data\15m\*.csv -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 3 Name, LastWriteTime

Write-Host "`n=== PG/SC 15m (degraded-path watch) ==="
foreach ($sym in @("PG", "SC")) {
    $path = Join-Path $root "data\15m\$sym.csv"
    if (-not (Test-Path -LiteralPath $path)) {
        Write-Host "$sym missing"
        continue
    }
    $fi = Get-Item -LiteralPath $path
    $tail = ""
    $tailDate = ""
    try {
        $tail = (Get-Content -LiteralPath $path -Tail 1 -Encoding UTF8)
        $parts = $tail -split ","
        if ($parts.Count -gt 0) { $tailDate = $parts[-1].Trim() }
    } catch {}
    Write-Host "$sym mtime=$($fi.LastWriteTime) bytes=$($fi.Length) tail_date=$tailDate"
}

Write-Host "`n=== DATA MANAGER LOG ==="
$dm = "runtime\logs\data_manager_futures.log"
if (-not (Test-Path $dm)) { $dm = "data_sync.log" }
if (Test-Path $dm) { Get-Content $dm -Tail 8 -Encoding UTF8 } else { Write-Host "no dm log" }

Write-Host "`n=== LC FILE ==="
Get-ChildItem data -Recurse -Filter "LC*.csv" | Select-Object FullName, LastWriteTime, Length | Format-Table -AutoSize
if (Test-Path "data\1d\LCUSDT.csv") { Get-Content "data\1d\LCUSDT.csv" -Tail 2 -Encoding UTF8 }

Write-Host "`n=== ACTIVE PENDING (first 10) ==="
if (Test-Path "runtime\fengji_pending_orders\pending_orders.json") {
    $po = Get-Content "runtime\fengji_pending_orders\pending_orders.json" -Raw -Encoding UTF8 | ConvertFrom-Json
    $active = $po | Where-Object { $_.status -in @("ACTIVE","READY_TRIGGERED") }
    Write-Host "active count: $($active.Count) / total $($po.Count)"
    $active | Select-Object -First 10 symbol, strategy_id, status, side, trigger_price, valid_until | Format-Table
    $lc = $po | Where-Object { $_.symbol -match "LC" }
    Write-Host "LC rows:"; $lc | Select-Object symbol, strategy_id, status, side, trigger_price, valid_until | Format-Table
}

Write-Host "`n=== PAPER STATE ==="
$ps = "runtime\fengji_futures\state_futures_v2.json"
if (Test-Path $ps) {
    $s = Get-Content $ps -Raw -Encoding UTF8 | ConvertFrom-Json
    $syms = $s.symbols.PSObject.Properties.Name
    Write-Host "symbols in paper: $($syms -join ', ')"
}
