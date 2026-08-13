param(
    [string]$Symbols = "DEFAULT",
    [int]$Days = 180,
    [int]$LookbackHours = 24,
    [switch]$RefreshOkx
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

$logDir = Join-Path $root "runtime\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir "crypto_combined_monitor.log"

$env:PYTHONPATH = "src;packages/fengji_core"

$guardPy = Join-Path $root "scripts\validate_crypto_okx_180d_cache.py"
if (Test-Path -LiteralPath $guardPy) {
    python $guardPy --dir (Join-Path $root "data\crypto_okx")
    if ($LASTEXITCODE -ne 0) {
        Write-Error "crypto 180d cache validation failed; abort monitor to avoid memory blow-up"
        exit 1
    }
}

$monitorPy = Join-Path $root "src\crypto_combined_monitor.py"
if (-not (Test-Path -LiteralPath $monitorPy)) {
    throw "monitor script not found: $monitorPy"
}

$argsList = @(
    $monitorPy,
    "--symbols", $Symbols,
    "--days", "$Days",
    "--lookback-hours", "$LookbackHours",
    "--out-dir", (Join-Path $root "results\crypto_combined_monitor")
)
if (-not $RefreshOkx) {
    $argsList += "--use-cache"
}

$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
try {
    $output = & python @argsList 2>&1 | Out-String
    $exitCode = $LASTEXITCODE
} catch {
    $output = $_.Exception.Message
    $exitCode = 1
}

$line = "[$stamp] exit=$exitCode symbols=$Symbols`n$output"
Add-Content -LiteralPath $logFile -Value $line.TrimEnd() -Encoding UTF8

if ($env:FENGJI_CRYPTO_COMBINED_MONITOR_QUIET -ne "1") {
    Write-Output $output.TrimEnd()
}

exit $exitCode
