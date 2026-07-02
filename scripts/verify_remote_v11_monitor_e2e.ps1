# V1.1 monitor E2E via SSH tunnel (pro token mint — avoids opens 429)
param(
    [string]$SshHost = "domestic-quant",
    [int]$LocalPort = 8043,
    [double]$PauseSec = 2.0
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $Root "scripts\verify_v11_monitor_e2e.py"
if (-not (Test-Path -LiteralPath $py)) {
    throw "Missing $py"
}

& python $py --ssh-tunnel $SshHost --local-port $LocalPort --pause-sec $PauseSec
exit $LASTEXITCODE
