# 国内 futures pending plan/apply 锁优化 + data_manager 15m 降级（仅同步相关文件）
param(
    [switch]$PendingOnly,
    [switch]$DataManagerOnly
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

$files = @()
if (-not $DataManagerOnly) {
    $files += "src/fengji_futures_pending_order_monitor.py"
}
if (-not $PendingOnly) {
    $files += "data_manager_futures.py"
}
$files += "scripts/check_domestic_status.ps1"
$files += "scripts/restart_domestic_pending_monitor.ps1"
$files += "scripts/restart_domestic_data_manager.ps1"
$files += "packages/fengji_core/fengji_core/constants.py"

$remoteRoot = "C:/Users/Administrator/quant_futures"
foreach ($rel in ($files | Select-Object -Unique)) {
    $local = Join-Path $root ($rel -replace "/", "\")
    if (-not (Test-Path -LiteralPath $local)) { throw "missing: $local" }
    $remote = "$remoteRoot/$($rel -replace '\\','/')"
    scp -o BatchMode=yes -o ConnectTimeout=20 $local "domestic-quant:$remote"
    if ($LASTEXITCODE -ne 0) { throw "scp failed: $rel" }
    Write-Host "synced domestic: $rel"
}

if (-not $DataManagerOnly) {
    ssh -o BatchMode=yes domestic-quant "powershell -NoProfile -File $remoteRoot/scripts/restart_domestic_pending_monitor.ps1"
}
if (-not $PendingOnly) {
    ssh -o BatchMode=yes domestic-quant "powershell -NoProfile -File $remoteRoot/scripts/restart_domestic_data_manager.ps1"
}

Write-Host "=== Done ===" -ForegroundColor Green
