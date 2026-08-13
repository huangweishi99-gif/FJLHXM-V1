param(
    [switch]$EmitSandbox
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

$logDir = Join-Path $root "runtime\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir "new10_fill_watch.log"

$env:PYTHONPATH = "scripts;src;packages/fengji_core;services"
$env:FENGJI_MARKET = "crypto"

$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$env:FENGJI_NEW10_WATCH_QUIET='1'
$syncPs = Join-Path $root "scripts\sync_overseas_paper_state.ps1"
$syncD1Ps = Join-Path $root "scripts\sync_overseas_crypto_1d_for_audit.ps1"
if (Test-Path -LiteralPath $syncPs) {
    $prevQuiet = $env:FENGJI_SYNC_QUIET
    $env:FENGJI_SYNC_QUIET = "1"
    try { & powershell -NoProfile -ExecutionPolicy Bypass -File $syncPs | Out-Null } catch { }
    if ($null -ne $prevQuiet) { $env:FENGJI_SYNC_QUIET = $prevQuiet } else { Remove-Item Env:FENGJI_SYNC_QUIET -ErrorAction SilentlyContinue }
}
if (Test-Path -LiteralPath $syncD1Ps) {
    try { & powershell -NoProfile -ExecutionPolicy Bypass -File $syncD1Ps | Out-Null } catch { }
}

$watchPy = Join-Path $root "scripts\watch_new10_crypto_fills.py"
if (-not (Test-Path -LiteralPath $watchPy)) {
    throw "watch script not found: $watchPy"
}

$argsList = @($watchPy)
if ($EmitSandbox) { $argsList += "--emit-sandbox" }

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

if ($env:FENGJI_NEW10_WATCH_QUIET -ne "1") {
    Write-Output $output.TrimEnd()
}

exit $exitCode
