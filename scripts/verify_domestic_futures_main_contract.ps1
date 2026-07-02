# Remote audit: domestic server futures main-contract manifest + sample CSV source check.
param(
    [string]$SshHost = "domestic-quant",
    [string]$RemoteRoot = "C:/Users/Administrator/quant_futures"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$localManifest = Join-Path $root "runtime\domestic_futures_main_contract_sources.json"
$reportJson = Join-Path $root "runtime\logs\futures_main_contract_audit_remote.json"

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $localManifest) | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $reportJson) | Out-Null

$remoteManifest = "$RemoteRoot/runtime/logs/futures_main_contract_sources.json"
scp -o BatchMode=yes -o ConnectTimeout=20 "${SshHost}:$remoteManifest" "$localManifest"
if ($LASTEXITCODE -ne 0) {
    throw "scp manifest failed"
}

$env:PYTHONPATH = "src;packages/fengji_core;services"
Set-Location $root
python scripts/verify_futures_main_contract_manifest.py --manifest $localManifest --json-out $reportJson
$auditExit = $LASTEXITCODE

Write-Host "=== sample CSV tail (AG/LH/RB) ===" -ForegroundColor Cyan
foreach ($sym in @("AG", "LH", "RB")) {
    ssh -o BatchMode=yes $SshHost "powershell -NoProfile -Command Get-Content $RemoteRoot/data/1d/$sym.csv -Tail 1"
}

Write-Host "=== data pump log tail ===" -ForegroundColor Cyan
ssh -o BatchMode=yes $SshHost "powershell -NoProfile -ExecutionPolicy Bypass -Command Get-Content $RemoteRoot/runtime/logs/data_manager_futures.log -Tail 3"

exit $auditExit
