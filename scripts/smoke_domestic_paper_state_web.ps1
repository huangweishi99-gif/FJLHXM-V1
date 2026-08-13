param(
    [int]$Port = 8021,
    [switch]$SkipSync
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

$syncScript = Join-Path $root "scripts\sync_domestic_paper_state.ps1"
$statePath = Join-Path $root "runtime\domestic_paper_state.json"
$logDir = Join-Path $root "runtime\logs"
$stdout = Join-Path $logDir "api_smoke_domestic_stdout.log"
$stderr = Join-Path $logDir "api_smoke_domestic_stderr.log"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

if (-not $SkipSync) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $syncScript
    if ($LASTEXITCODE -ne 0) {
        throw "domestic paper_state sync failed with exit code $LASTEXITCODE"
    }
}

if (-not (Test-Path -LiteralPath $statePath)) {
    throw "local domestic paper_state not found: $statePath"
}

$env:PYTHONPATH = "src;packages/fengji_core;services"
if (Test-Path -LiteralPath $stdout) { Remove-Item -LiteralPath $stdout -Force }
if (Test-Path -LiteralPath $stderr) { Remove-Item -LiteralPath $stderr -Force }

$proc = Start-Process `
    -FilePath "python" `
    -ArgumentList @("-m", "uvicorn", "services.api.main:app", "--host", "127.0.0.1", "--port", "$Port") `
    -PassThru `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr

try {
    $response = $null
    for ($i = 0; $i -lt 25; $i++) {
        Start-Sleep -Milliseconds 500
        try {
            $response = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/monitor/domestic/latest-opens" -TimeoutSec 3
            break
        } catch {
            if ($proc.HasExited) {
                throw "uvicorn exited early; check $stderr"
            }
        }
    }

    if ($null -eq $response) {
        throw "domestic monitor API did not become ready"
    }
    if ($response.source -ne "paper_state") {
        throw "expected source=paper_state, got source=$($response.source)"
    }

    $positions = @($response.positions)
    if ($positions.Count -le 0) {
        throw "expected at least one domestic open position"
    }

    $metaPath = Join-Path $root "runtime\domestic_paper_state_meta.json"
    $meta = $null
    if (Test-Path -LiteralPath $metaPath) {
        $meta = Get-Content -LiteralPath $metaPath -Raw -Encoding UTF8 | ConvertFrom-Json
    }

    Write-Host "DOMESTIC_WEB_SMOKE_OK"
    Write-Host ("source={0}" -f $response.source)
    Write-Host ("positions={0}" -f $positions.Count)
    if ($meta) {
        Write-Host ("synced_at={0}" -f $meta.synced_at)
        Write-Host ("symbols={0}" -f $meta.symbols)
        Write-Host ("open_positions_meta={0}" -f $meta.open_positions)
    }
    exit 0
} finally {
    if ($proc -and -not $proc.HasExited) {
        Stop-Process -Id $proc.Id -Force
        Wait-Process -Id $proc.Id -ErrorAction SilentlyContinue
    }
}
