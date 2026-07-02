# 将本地 PG context（含 exit_price 回填）同步到国内服务器并刷新 Web/API。
param(
    [string]$SshAlias = "domestic-quant",
    [string]$RemoteRoot = "C:\Users\Administrator\quant_futures",
    [switch]$SkipDump,
    [switch]$SkipRestore,
    [switch]$SkipDeploy
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$dumpLocal = Join-Path $Root "runtime\secrets\fengji_pg_context_refresh.dump"
$dumpRemote = Join-Path $RemoteRoot "runtime\secrets\fengji_pg_context_refresh.dump"
$remoteRootWin = $RemoteRoot

Write-Host "=== PG context refresh -> $SshAlias ===" -ForegroundColor Cyan

if (-not $SkipDump) {
    Write-Host "[1/5] Export local Docker PG ..." -ForegroundColor Cyan
    $dumpPath = & powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "export_local_pg_dump.ps1") |
        Select-Object -Last 1
    if (-not (Test-Path -LiteralPath $dumpPath)) {
        throw "pg dump not found: $dumpPath"
    }
    New-Item -ItemType Directory -Force -Path (Split-Path $dumpLocal -Parent) | Out-Null
    Copy-Item -LiteralPath $dumpPath -Destination $dumpLocal -Force
    Write-Host "  Dump -> $dumpLocal" -ForegroundColor DarkGray
} else {
    Write-Host "[1/5] Skip dump (-SkipDump)" -ForegroundColor DarkGray
    if (-not (Test-Path -LiteralPath $dumpLocal)) {
        throw "Missing dump: $dumpLocal"
    }
}

if (-not $SkipDeploy) {
    Write-Host "[2/5] Sync API manifest + web/ ..." -ForegroundColor Cyan
    & powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "sync_deploy_fengji_api.ps1") `
        -SshAlias $SshAlias -RemoteRoot $RemoteRoot -SyncWeb -RestartApi
} else {
    Write-Host "[2/5] Skip deploy (-SkipDeploy)" -ForegroundColor DarkGray
}

if (-not $SkipRestore) {
    Write-Host "[3/5] Upload pg_dump ..." -ForegroundColor Cyan
    $scpRemote = ($dumpRemote -replace "\\", "/") -replace "^([A-Za-z]):", '/$1:'
    & scp -o BatchMode=yes $dumpLocal "${SshAlias}:${scpRemote}"
    if ($LASTEXITCODE -ne 0) { throw "scp dump failed" }

    Write-Host "[4/5] Restore on server ..." -ForegroundColor Cyan
    $restoreScript = Join-Path $remoteRootWin "scripts\remote\restore_fengji_pg_dump.ps1"
    ssh -o BatchMode=yes $SshAlias "powershell -NoProfile -ExecutionPolicy Bypass -File `"$restoreScript`" -DumpPath `"$dumpRemote`""
    $grantScript = Join-Path $remoteRootWin "scripts\remote\grant_fengji_pg_privileges.ps1"
    ssh -o BatchMode=yes $SshAlias "powershell -NoProfile -ExecutionPolicy Bypass -File `"$grantScript`""
} else {
    Write-Host "[3-4/5] Skip restore (-SkipRestore)" -ForegroundColor DarkGray
}

Write-Host "[5/5] Remote health + exit_price spot-check ..." -ForegroundColor Cyan
ssh -o BatchMode=yes $SshAlias "powershell -NoProfile -ExecutionPolicy Bypass -File `"$($remoteRootWin)\scripts\verify_fengji_api_health.ps1`""

Write-Host "`nPG context refresh sync done." -ForegroundColor Green
Write-Host "Optional: run smoke_pg_api_consistency against remote base URL." -ForegroundColor Yellow
