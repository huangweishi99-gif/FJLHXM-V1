param(
    [string]$SshHost = "overseas-quant",
    [string]$RemoteRoot = "/home/ubuntu/quant_crypto",
    [int]$SinceHours = 168,
    [string]$LocalOut = ""
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

$argsList = @(
    (Join-Path $root "scripts\sync_overseas_fill_events.py"),
    "--ssh-host", $SshHost,
    "--remote-root", $RemoteRoot,
    "--since-hours", "$SinceHours"
)
if ($LocalOut) { $argsList += @("--out", $LocalOut) }

python @argsList
exit $LASTEXITCODE
