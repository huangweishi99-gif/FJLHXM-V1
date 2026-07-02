# Post-deploy smoke: domestic chart API must expose solidified OS state overlay.
param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$Symbol = "RB",
    [string]$StateDir = "C:\Users\Administrator\quant_futures\runtime\fengji_os_state"
)

$ErrorActionPreference = "Stop"
$uri = "$BaseUrl/api/v1/monitor/domestic/chart?symbol=$Symbol&strategy_id=DS03&market=FUTURES&years=2"
$bundle = Invoke-RestMethod -Uri $uri -TimeoutSec 180
$os = $bundle.os_state
if (-not $os) { throw "missing os_state in chart bundle" }
if (-not $os.used_os_state) { throw "os_state.used_os_state is false: $($os | ConvertTo-Json -Compress)" }

Write-Host "CHART_OS_STATE_OK symbol=$Symbol used=$($os.used_os_state) camp=$($os.camp) confirmed=$($os.camp_confirmed) last=$($os.last_date) hardened=$($os.hardened_count) bars=$($bundle.bars.Count) segments=$($bundle.hardened_segments.Count)"

$root = Split-Path -Parent $PSScriptRoot
$verifyPy = Join-Path $root "scripts\verify_os_state_snapshot.py"
if (-not (Test-Path $verifyPy)) {
    $verifyPy = Join-Path (Get-Location) "scripts\verify_os_state_snapshot.py"
}
foreach ($tf in @("1d", "1h", "15m")) {
    python $verifyPy --state-dir $StateDir --symbol $Symbol --timeframe $tf
    if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 2) {
        throw "verify_os_state_snapshot failed for ${Symbol}_${tf} exit=$LASTEXITCODE"
    }
}

exit 0
