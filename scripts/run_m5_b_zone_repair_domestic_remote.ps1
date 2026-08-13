# Run on domestic-quant: M5 B-zone repair (dry-run or apply).
param([switch]$Apply)

$ErrorActionPreference = "Stop"
Set-Location "C:\Users\Administrator\quant_futures"
$env:PYTHONPATH = "src;packages\fengji_core"

$disp = Get-Content "runtime\m5_b_zone_disposition.json" -Raw | ConvertFrom-Json
$ids = ($disp.by_profile.domestic -join ",")
$reason = $disp.repair_reason
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$out = "runtime/m5_b_zone_repair_domestic_$stamp.json"
$paperState = "runtime/fengji_futures/state_futures_v2.json"
$monitorState = "runtime/fengji_pending_orders/futures_pending_state.json"

$args = @(
    "scripts/repair_corrupt_futures_state_from_audit.py",
    "--audit", "runtime/m5_empty_audit.json",
    "--state", $paperState,
    "--monitor-state", $monitorState,
    "--order-id", $ids,
    "--reason", $reason,
    "--out", $out
)
if ($Apply) { $args += "--apply" }
& py -3 @args
Write-Host "plan=$out apply=$($Apply.IsPresent) ids=$($disp.by_profile.domestic.Count)"
exit $LASTEXITCODE
