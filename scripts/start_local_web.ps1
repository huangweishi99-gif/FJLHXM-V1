# 本地 Web + API 一键启动（推荐 8001，避免 8000 旧进程未更新）
param(
    [int]$Port = 8001,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$env:PYTHONPATH = "src;packages/fengji_core;services"
$env:FENGJI_AUTH_ALLOW_DEV_SECRET = "1"

$listening = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if (-not $listening) {
    Write-Host "Starting FengJi API on http://127.0.0.1:$Port ..." -ForegroundColor Cyan
    Start-Process -FilePath "python" -ArgumentList @(
        "-m", "uvicorn", "services.api.main:app",
        "--host", "127.0.0.1", "--port", "$Port", "--reload"
    ) -WorkingDirectory $Root -WindowStyle Minimized
    Start-Sleep -Seconds 3
} else {
    Write-Host "Port $Port already listening — using existing API." -ForegroundColor Yellow
}

$url = "http://127.0.0.1:$Port/web/index.html"
Write-Host "Open: $url" -ForegroundColor Green
Write-Host "Tip: 若仍看到旧图，请确认不是打开 8000；8000 可能是旧 API。" -ForegroundColor Yellow

if (-not $NoBrowser) {
    Start-Process $url
}
