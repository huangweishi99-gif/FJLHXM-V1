param(
    [int]$Port = 8000,
    [string]$BindHost = "127.0.0.1",
    [switch]$Reload
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

$logDir = Join-Path $root "runtime\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$localEnv = Join-Path $root "runtime\secrets\fengji_local.env"
if (Test-Path -LiteralPath $localEnv) {
    Get-Content -LiteralPath $localEnv -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        if ($line -match "^([^=]+)=(.*)$") {
            Set-Item -Path ("env:" + $matches[1].Trim()) -Value $matches[2].Trim()
        }
    }
}

$env:PYTHONPATH = "src;packages/fengji_core;services"
if (-not $env:FENGJI_JWT_SECRET -and -not $env:FENGJI_AUTH_ALLOW_DEV_SECRET) {
    Write-Host "WARN: FENGJI_JWT_SECRET unset; using dev fallback FENGJI_AUTH_ALLOW_DEV_SECRET=1 (local only)" -ForegroundColor Yellow
    $env:FENGJI_AUTH_ALLOW_DEV_SECRET = "1"
}

$args = @("-m", "uvicorn", "services.api.main:app", "--host", $BindHost, "--port", "$Port")
if ($Reload) { $args += "--reload" }

Write-Host "Starting FengJi API on http://${BindHost}:$Port ..." -ForegroundColor Cyan
Write-Host "Health: http://${BindHost}:$Port/api/v1/health" -ForegroundColor DarkGray
python @args
