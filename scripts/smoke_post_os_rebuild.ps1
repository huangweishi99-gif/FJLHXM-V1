# Post OS rebuild smoke: domestic RB + overseas IOUSDT camp alignment + runtime freshness
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "[1/4] overseas runtime ..." -ForegroundColor Cyan
& (Join-Path $Root "scripts\check_overseas_runtime_status.ps1") | Select-Object -Last 15

Write-Host "`n[2/4] overseas IOUSDT / BNB OS snapshot ..." -ForegroundColor Cyan
scp -o BatchMode=yes (Join-Path $Root "scripts\verify_os_state_snapshot.py") "overseas-quant:/home/ubuntu/quant_crypto/scripts/verify_os_state_snapshot.py" | Out-Null
ssh -o BatchMode=yes overseas-quant "cd /home/ubuntu/quant_crypto && .venv/bin/python scripts/verify_os_state_snapshot.py --symbol IOUSDT --since 2026-01"
$iousdtExit = $LASTEXITCODE
ssh -o BatchMode=yes overseas-quant "cd /home/ubuntu/quant_crypto && .venv/bin/python scripts/verify_os_state_snapshot.py --symbol BNBUSDT --since 2026-06"
if ($iousdtExit -ne 0) { throw "IOUSDT camp/camp_confirmed mismatch" }

Write-Host "`n[3/4] domestic runtime + RB OS snapshot ..." -ForegroundColor Cyan
scp -o BatchMode=yes (Join-Path $Root "scripts\verify_os_state_snapshot.py") "domestic-quant:C:/Users/Administrator/quant_futures/scripts/verify_os_state_snapshot.py" | Out-Null
ssh -o BatchMode=yes domestic-quant "powershell -NoProfile -ExecutionPolicy Bypass -File C:/Users/Administrator/quant_futures/scripts/check_domestic_status.ps1" | Select-Object -Last 25
ssh -o BatchMode=yes domestic-quant "powershell -NoProfile -Command `"python C:/Users/Administrator/quant_futures/scripts/verify_os_state_snapshot.py --state-dir C:/Users/Administrator/quant_futures/runtime/fengji_os_state --symbol RB --since 2026-02`""
if ($LASTEXITCODE -ne 0) { throw "Domestic RB OS snapshot verification failed" }

Write-Host "`n[4/4] POST_OS_REBUILD_SMOKE_OK" -ForegroundColor Green
