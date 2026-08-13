# Deploy watchdog fix to domestic server. Restarts ONLY data_manager (not paper/radar/pending).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$RemoteHost = "domestic-quant"
$RemoteRoot = "C:/Users/Administrator/quant_futures"

$files = @(
    "data_manager_futures.py",
    "scripts/watchdog_domestic.ps1",
    "scripts/ensure_single_data_manager.ps1",
    "scripts/install_watchdog_domestic_task.ps1",
    "scripts/verify_domestic_watchdog.ps1",
    "scripts/check_domestic_status.ps1"
)

Write-Host "[1/5] sync files..." -ForegroundColor Cyan
foreach ($rel in $files) {
    $local = Join-Path $Root ($rel -replace "/", "\")
    if (-not (Test-Path $local)) { throw "Missing $local" }
    $remotePath = "$RemoteRoot/$($rel -replace '\\','/')"
    scp -o BatchMode=yes -o ConnectTimeout=15 "$local" "${RemoteHost}:$remotePath"
    Write-Host "  OK $rel" -ForegroundColor DarkGray
}

Write-Host "[2/5] reinstall watchdog task (Administrator)..." -ForegroundColor Cyan
ssh -o BatchMode=yes -o ConnectTimeout=20 $RemoteHost "powershell -NoProfile -ExecutionPolicy Bypass -File '$RemoteRoot/scripts/install_watchdog_domestic_task.ps1'"

Write-Host "[3/5] restart data_manager only (paper/radar/pending untouched)..." -ForegroundColor Cyan
ssh -o BatchMode=yes -o ConnectTimeout=30 $RemoteHost "powershell -NoProfile -ExecutionPolicy Bypass -File '$RemoteRoot/scripts/ensure_single_data_manager.ps1'"

Write-Host "[4/5] clear stale alerts..." -ForegroundColor Cyan
ssh -o BatchMode=yes -o ConnectTimeout=15 $RemoteHost "powershell -NoProfile -Command `"Remove-Item '$RemoteRoot/runtime/watchdog/proc_data_manager.alert','$RemoteRoot/runtime/watchdog/data_stale.alert' -ErrorAction SilentlyContinue`""

Write-Host "[5/5] verify..." -ForegroundColor Cyan
ssh -o BatchMode=yes -o ConnectTimeout=45 $RemoteHost "powershell -NoProfile -ExecutionPolicy Bypass -File '$RemoteRoot/scripts/verify_domestic_watchdog.ps1'"

Write-Host "`nDeploy done." -ForegroundColor Green
