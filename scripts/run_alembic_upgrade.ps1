# Server-side: load fengji_api.env and run alembic upgrade head.
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
} else {
    throw "Missing $envFile"
}

if (-not $env:DATABASE_URL) {
    throw "DATABASE_URL not set in fengji_api.env"
}

$env:PYTHONPATH = "src;packages/fengji_core;services"
python -m alembic -c alembic.ini upgrade head
python -m alembic -c alembic.ini current
