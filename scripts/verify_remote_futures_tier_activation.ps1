param(
    [string]$SshAlias = "domestic-quant",
    [string]$RemoteRoot = "C:\Users\Administrator\quant_futures"
)

$ErrorActionPreference = "Stop"
$remoteRootWin = $RemoteRoot
$script = Join-Path $remoteRootWin "scripts\verify_futures_tier_activation.py"
ssh -o BatchMode=yes $SshAlias "powershell -NoProfile -Command `"Set-Location '$remoteRootWin'; `$env:PYTHONPATH='src;packages/fengji_core;services'; python '$script'`""
