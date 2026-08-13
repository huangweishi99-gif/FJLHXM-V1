param(
    [switch]$DryRun,
    [switch]$ResetState
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

$logDir = Join-Path $root "runtime\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir "ds09_live_watch.log"

$env:PYTHONPATH = "scripts;src;packages/fengji_core;services"
$env:FENGJI_MARKET = "crypto"

$watchPy = Join-Path $root "scripts\watch_ds09_live_radar_sandbox.py"
if (-not (Test-Path -LiteralPath $watchPy)) {
    throw "watch script not found: $watchPy"
}

$argsList = @($watchPy, "--once")
if ($DryRun) { $argsList += "--dry-run" }
if ($ResetState) { $argsList += "--reset-state" }

$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
try {
    $output = & python @argsList 2>&1 | Out-String
    $exitCode = $LASTEXITCODE
} catch {
    $output = $_.Exception.Message
    $exitCode = 1
}

$line = "[$stamp] exit=$exitCode`n$output"
Add-Content -LiteralPath $logFile -Value $line.TrimEnd() -Encoding UTF8

if ($env:FENGJI_DS09_WATCH_QUIET -ne "1") {
    Write-Output $output.TrimEnd()
}

exit $exitCode
