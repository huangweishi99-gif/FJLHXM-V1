# Server-side: probe API import and health (diagnostics only).
param(
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
python -c "import services.api.main as m; print('import_ok', m.app.title)"
try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/health" -TimeoutSec 5
    Write-Host "health_ok $($health.status)"
} catch {
    Write-Host "health_fail $($_.Exception.Message)"
}
