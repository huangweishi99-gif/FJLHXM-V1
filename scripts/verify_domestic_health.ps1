# 本机一键：国内运行态 + PG/SC 15m 验收 + 关键进程
param(
    [string]$SshHost = "domestic-quant",
    [string]$RemoteRoot = "C:/Users/Administrator/quant_futures"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

Write-Host "=== domestic status ===" -ForegroundColor Cyan
& (Join-Path $root "scripts\check_domestic_runtime_remote.ps1") -SshHost $SshHost -RemoteRoot $RemoteRoot
if ($LASTEXITCODE -ge 2) { throw "check_domestic_runtime_remote hard fail: $LASTEXITCODE" }

# PG/SC acceptance already runs inside check_domestic_runtime_remote; exit 1 = PENDING only.
if ($LASTEXITCODE -eq 1) {
    Write-Host "PG/SC acceptance pending (market closed or not yet written)" -ForegroundColor Yellow
}

Write-Host "`n=== domestic health OK ===" -ForegroundColor Green
