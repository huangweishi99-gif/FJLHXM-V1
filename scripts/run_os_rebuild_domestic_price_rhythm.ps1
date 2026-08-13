# Rebuild domestic futures OS state after os_engine price-rhythm fix.
$ErrorActionPreference = "Stop"
$Root = "C:/Users/Administrator/quant_futures"
Set-Location $Root

$env:PYTHONPATH = "$Root/src;$Root/packages/fengji_core"
$env:FENGJI_MARKET = "futures"
python -c "from fengji_core.os_engine import FengJiOSIdentityEngine; assert hasattr(FengJiOSIdentityEngine, '_can_connect_opposite_nodes'); print('OS_ENGINE_OK')"

& "$Root/scripts/stop_domestic_futures_runtime.ps1"
Start-Sleep -Seconds 2

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backup = "runtime/fengji_os_state_backup_$stamp"
$rebuild = "runtime/fengji_os_state_rebuild_$stamp"
Copy-Item -LiteralPath "runtime/fengji_os_state" -Destination $backup -Recurse -Force

python scripts/rebuild_os_state_all.py `
  --input data/1d,market=futures `
  --input data/1h,market=futures `
  --input data/15m,market=futures `
  --state-dir $rebuild `
  --mode rebuild

Remove-Item -LiteralPath "runtime/fengji_os_state" -Recurse -Force
Copy-Item -LiteralPath $rebuild -Destination "runtime/fengji_os_state" -Recurse
Write-Host "SWAPPED_TO=$rebuild BACKUP=$backup"

powershell -NoProfile -ExecutionPolicy Bypass -File "$Root/scripts/restart_domestic_futures_runtime.ps1"
