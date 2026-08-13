# Run repair dry-run / apply for M5 A-zone order_ids on remote servers.
param(
    [ValidateSet("domestic", "overseas")]
    [string]$Profile,
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Disposition = Join-Path $Root "runtime\m5_a_zone_disposition.json"
if (-not (Test-Path $Disposition)) {
    throw "Missing $Disposition — run apply_m5_a_zone_audit_invalid.py first"
}
$payload = Get-Content $Disposition -Raw | ConvertFrom-Json
$ids = @($payload.by_profile.$Profile)
if ($ids.Count -eq 0) {
    Write-Host "No order_ids for profile=$Profile"
    exit 0
}
$orderArg = ($ids -join ",")
$reason = $payload.repair_reason

if ($Profile -eq "domestic") {
    $Remote = "domestic-quant"
    $RemoteRoot = "C:/Users/Administrator/quant_futures"
    $state = "$RemoteRoot/runtime/state_futures_v2.json"
    $monitor = "$RemoteRoot/runtime/fengji_pending_orders/state.json"
    $py = "py -3"
} else {
    $Remote = "overseas-quant"
    $RemoteRoot = "/home/ubuntu/quant_crypto"
    $state = "$RemoteRoot/runtime/fengji_paper/state.json"
    $monitor = "$RemoteRoot/runtime/fengji_pending_orders/state.json"
    $py = ".venv/bin/python"
}

# sync helper files
scp -o BatchMode=yes (Join-Path $Root "runtime\m5_empty_audit.json") "${Remote}:${RemoteRoot}/runtime/m5_empty_audit.json"
scp -o BatchMode=yes (Join-Path $Root "scripts\repair_corrupt_futures_state_from_audit.py") "${Remote}:${RemoteRoot}/scripts/repair_corrupt_futures_state_from_audit.py"

$applyFlag = if ($Apply) { "--apply" } else { "" }
$outName = "m5_a_zone_repair_${Profile}_$(Get-Date -Format 'yyyyMMdd_HHmmss').json"

if ($Profile -eq "domestic") {
    $cmd = @"
cd /d $RemoteRoot && set PYTHONPATH=src;packages\fengji_core && $py scripts\repair_corrupt_futures_state_from_audit.py --audit runtime\m5_empty_audit.json --state runtime\state_futures_v2.json --monitor-state runtime\fengji_pending_orders\state.json --order-id $orderArg --reason "$reason" --out runtime\$outName $applyFlag
"@
    ssh -o BatchMode=yes $Remote "cmd /c `"$cmd`""
} else {
    $cmd = "cd $RemoteRoot && PYTHONPATH=src:packages/fengji_core $py scripts/repair_corrupt_futures_state_from_audit.py --audit runtime/m5_empty_audit.json --state runtime/fengji_paper/state.json --monitor-state runtime/fengji_pending_orders/state.json --order-id '$orderArg' --reason '$reason' --out runtime/$outName $applyFlag"
    ssh -o BatchMode=yes $Remote $cmd
}

Write-Host "profile=$Profile apply=$($Apply.IsPresent) ids=$($ids.Count)"
