# W17 P1 bootstrap: PG reverse tunnel (local Docker) + server env + deploy + acceptance.
# Production should install PostgreSQL on the server; this tunnel mode is for unblocking acceptance.
param(
    [string]$SshAlias = "domestic-quant",
    [string]$RemoteRoot = "C:\Users\Administrator\quant_futures",
    [int]$LocalPgPort = 5432,
    [int]$RemotePgTunnelPort = 15432,
    [int]$AcceptanceLocalPort = 8040,
    [switch]$SkipAcceptance,
    [switch]$SkipTunnel,
    [switch]$AllowManualSubscriptionConfirm
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Test-LocalPg {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        return $true
    } catch {
        # ignore
    }
    $dc = docker compose ps --format json 2>$null | ConvertFrom-Json
    if ($dc -and $dc.State -eq "running") { return $true }
    $ping = docker exec fengji_pg pg_isready -U fengji -d fengji 2>$null
    return $LASTEXITCODE -eq 0
}

Write-Host "=== W17 P1 bootstrap (domestic) ===" -ForegroundColor Cyan

if (-not $SkipTunnel) {
    Write-Host "[1/6] Start SSH reverse tunnel ..." -ForegroundColor Cyan
    & powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "start_pg_reverse_tunnel.ps1") -SshAlias $SshAlias -LocalPgPort $LocalPgPort -RemotePgTunnelPort $RemotePgTunnelPort
    Start-Sleep -Seconds 2
} else {
    Write-Host "[1/6] Skip PG tunnel (-SkipTunnel)" -ForegroundColor DarkGray
}

Write-Host "[2/6] Sync deploy manifest + web ..." -ForegroundColor Cyan
& powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "sync_deploy_fengji_api.ps1") -SshAlias $SshAlias -RemoteRoot $RemoteRoot -SyncWeb

$remoteRootWin = $RemoteRoot
$remoteScript = Join-Path $RemoteRoot "scripts\remote\create_fengji_api_env.ps1"
$dbUrl = "postgresql+psycopg://fengji:fengji_dev@127.0.0.1:${RemotePgTunnelPort}/fengji"

Write-Host "[3/6] Install API deps on server ..." -ForegroundColor Cyan
ssh -o BatchMode=yes $SshAlias "powershell -NoProfile -ExecutionPolicy Bypass -File `"$remoteRootWin\scripts\install_fengji_api_deps.ps1`""

Write-Host "[4/6] Create fengji_api.env on server (secrets server-local) ..." -ForegroundColor Cyan
$manualFlag = if ($AllowManualSubscriptionConfirm) { "-AllowManualSubscriptionConfirm" } else { "" }
$createCmd = "powershell -NoProfile -ExecutionPolicy Bypass -File `"$remoteRootWin\scripts\remote\create_fengji_api_env.ps1`" -DatabaseUrl `"$dbUrl`" $manualFlag"
ssh -o BatchMode=yes $SshAlias $createCmd

Write-Host "[5/6] Migration + install task + restart API + verify ..." -ForegroundColor Cyan
& powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "sync_deploy_fengji_api.ps1") `
    -SshAlias $SshAlias -RemoteRoot $RemoteRoot -RunMigration -InstallTask -RestartApi -Verify

if (-not $SkipAcceptance) {
    Write-Host "[6/6] W17 remote acceptance via SSH tunnel ..." -ForegroundColor Cyan
    python (Join-Path $PSScriptRoot "w17_remote_acceptance.py") --ssh-tunnel $SshAlias --local-port $AcceptanceLocalPort --wait-seconds 8
} else {
    Write-Host "[6/6] Skip acceptance (-SkipAcceptance)" -ForegroundColor DarkGray
}

Write-Host "`nP1 bootstrap finished." -ForegroundColor Green
Write-Host "NOTE: PG via reverse tunnel is temporary. Install PostgreSQL on server for production." -ForegroundColor Yellow
Write-Host "Keep the ssh -R tunnel process running while the remote API uses local Docker PG." -ForegroundColor Yellow
