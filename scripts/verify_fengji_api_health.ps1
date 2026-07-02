# Server-side health check for FengJi Web API (W17-prod deploy verify).
param(
    [int]$Port = 8000,
    [string]$Root = "C:\Users\Administrator\quant_futures"
)

$ErrorActionPreference = "Stop"
Set-Location $Root

$envFile = Join-Path $Root "runtime\secrets\fengji_api.env"
if (Test-Path -LiteralPath $envFile) {
    Get-Content -LiteralPath $envFile -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        if ($line -match "^([^=]+)=(.*)$") {
            Set-Item -Path ("env:" + $matches[1].Trim()) -Value $matches[2].Trim()
        }
    }
}
$env:PYTHONPATH = "src;packages/fengji_core;services"

$healthUrl = "http://127.0.0.1:$Port/api/v1/health"
$health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 10
if ($health.status -ne "ok") {
    throw "health check failed: $($health | ConvertTo-Json -Compress)"
}

Write-Host "FENGJI_API_HEALTH_OK status=$($health.status) version=$($health.version)"

try {
    $current = python -m alembic -c alembic.ini current 2>&1 | Out-String
    if ($LASTEXITCODE -eq 0 -and $current -match "head") {
        Write-Host "ALEMBIC_CURRENT $($current.Trim())"
    } else {
        Write-Host "WARN: alembic current failed" -ForegroundColor Yellow
    }
} catch {
    Write-Host "WARN: alembic current failed (DATABASE_URL configured?)" -ForegroundColor Yellow
}

try {
    $stats = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/monitor/ws/stats" -TimeoutSec 10
    Write-Host "MONITOR_WS_STATS_OK connections=$($stats.active_connections)"
} catch {
    Write-Host "WARN: monitor ws stats unavailable (non-fatal for auth-only deploy)" -ForegroundColor Yellow
}

exit 0
