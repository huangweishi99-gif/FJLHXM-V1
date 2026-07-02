# W17 P2: install PostgreSQL on domestic server (replace 15432 reverse tunnel).
param(
    [string]$SshAlias = "domestic-quant",
    [string]$RemoteRoot = "C:\Users\Administrator\quant_futures",
    [int]$PgPort = 5432,
    [int]$AcceptanceLocalPort = 8040,
    [switch]$SkipDump,
    [switch]$SkipInstall,
    [switch]$SkipInstallerUpload,
    [switch]$SkipAcceptance,
    [switch]$AllowManualSubscriptionConfirm
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$remoteRootWin = $RemoteRoot
$dumpLocal = Join-Path $Root "runtime\secrets\fengji_pg_bootstrap.dump"
$dumpRemote = Join-Path $RemoteRoot "runtime\secrets\fengji_pg_bootstrap.dump"

Write-Host "=== W17 P2 bootstrap (server-local PostgreSQL) ===" -ForegroundColor Cyan

$useDockerDevPassword = $false
if (-not $SkipDump) {
    Write-Host "[1/7] pg_dump from local Docker fengji_pg (optional data seed) ..." -ForegroundColor Cyan
    docker exec fengji_pg pg_isready -U fengji -d fengji 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        New-Item -ItemType Directory -Force -Path (Split-Path $dumpLocal -Parent) | Out-Null
        docker exec fengji_pg pg_dump -U fengji -d fengji -Fc -f /tmp/fengji_pg_bootstrap.dump
        if ($LASTEXITCODE -ne 0) { throw "docker pg_dump failed" }
        docker cp fengji_pg:/tmp/fengji_pg_bootstrap.dump $dumpLocal
        if ($LASTEXITCODE -ne 0) { throw "docker cp dump failed" }
        $useDockerDevPassword = $true
        Write-Host "  Dump -> runtime/secrets/fengji_pg_bootstrap.dump" -ForegroundColor DarkGray
    } else {
        Write-Host "  Local Docker PG not running — skip dump (fresh schema via alembic)." -ForegroundColor Yellow
    }
} else {
    Write-Host "[1/7] Skip local pg_dump (-SkipDump)" -ForegroundColor DarkGray
}

Write-Host "[2/7] Sync deploy manifest + remote PG scripts ..." -ForegroundColor Cyan
& powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "sync_deploy_fengji_api.ps1") -SshAlias $SshAlias -RemoteRoot $RemoteRoot

if ((Test-Path -LiteralPath $dumpLocal) -and -not $SkipDump) {
    Write-Host "[3/7] Upload pg_dump to server ..." -ForegroundColor Cyan
    $scpRemote = ($dumpRemote -replace "\\", "/") -replace "^([A-Za-z]):", '/$1:'
    & scp -o BatchMode=yes $dumpLocal "${SshAlias}:${scpRemote}"
    if ($LASTEXITCODE -ne 0) { throw "scp dump failed" }
} else {
    Write-Host "[3/7] No dump to upload" -ForegroundColor DarkGray
}

$installFlag = if ($SkipInstall) { "" } else { "-Install" }
$dumpArg = if ((Test-Path -LiteralPath $dumpLocal) -and -not $SkipDump) { "-DumpPath `"$dumpRemote`"" } else { "" }
$installerArg = ""
if (-not $SkipInstall -and -not $SkipInstallerUpload) {
    $installerLocal = Join-Path $Root "runtime\secrets\postgresql-16.6-1-windows-x64.exe"
    $installerRemote = Join-Path $RemoteRoot "runtime\secrets\postgresql-16.6-1-windows-x64.exe"
    $needUpload = $true
    if (Test-Path -LiteralPath $installerLocal) {
        $localSize = (Get-Item -LiteralPath $installerLocal).Length
        $remoteSizeRaw = ssh -o BatchMode=yes $SshAlias "powershell -NoProfile -Command \"if (Test-Path '$installerRemote') { (Get-Item '$installerRemote').Length } else { 0 }\""
        $remoteSize = [long]($remoteSizeRaw.Trim())
        if ($remoteSize -ge ($localSize - 1024)) {
            $needUpload = $false
            Write-Host "[2b/7] Installer already on server ($([math]::Round($remoteSize/1MB,1)) MB) — skip upload" -ForegroundColor DarkGray
            $installerArg = "-InstallerPath `"$installerRemote`""
        }
    }
    if ($needUpload -and (Test-Path -LiteralPath $installerLocal)) {
        Write-Host "[2b/7] Upload PostgreSQL installer to server ..." -ForegroundColor Cyan
        $scpInst = ($installerRemote -replace "\\", "/") -replace "^([A-Za-z]):", '/$1:'
        & scp -o BatchMode=yes $installerLocal "${SshAlias}:${scpInst}"
        if ($LASTEXITCODE -ne 0) { throw "scp installer failed" }
        $installerArg = "-InstallerPath `"$installerRemote`""
    }
} elseif (-not $SkipInstall) {
    $installerRemote = Join-Path $RemoteRoot "runtime\secrets\postgresql-16.6-1-windows-x64.exe"
    $installerArg = "-InstallerPath `"$installerRemote`""
    Write-Host "[2b/7] Skip installer upload (-SkipInstallerUpload); use server copy" -ForegroundColor DarkGray
}

if ($useDockerDevPassword) {
    Write-Host "[3b] Seed server PG password file (docker fengji_dev) ..." -ForegroundColor Cyan
    $seedScript = Join-Path $remoteRootWin "scripts\remote\seed_fengji_pg_password.ps1"
    ssh -o BatchMode=yes $SshAlias "powershell -NoProfile -ExecutionPolicy Bypass -File `"$seedScript`" -Password fengji_dev"
}

Write-Host "[4/7] setup_domestic_postgresql.ps1 on server ..." -ForegroundColor Cyan
$setupScript = Join-Path $remoteRootWin "scripts\remote\setup_domestic_postgresql.ps1"
$setupCmd = "powershell -NoProfile -ExecutionPolicy Bypass -File `"$setupScript`" -PgPort $PgPort $installFlag $dumpArg $installerArg"
ssh -o BatchMode=yes $SshAlias $setupCmd
if ($LASTEXITCODE -ne 0) {
    throw "setup_domestic_postgresql failed — DATABASE_URL not patched (still on tunnel if unchanged)."
}

Write-Host "[5/7] Patch DATABASE_URL -> 127.0.0.1:$PgPort (keep JWT/ADMIN) ..." -ForegroundColor Cyan
$patchScript = Join-Path $remoteRootWin "scripts\remote\patch_fengji_api_env_from_pg_secret.ps1"
ssh -o BatchMode=yes $SshAlias "powershell -NoProfile -ExecutionPolicy Bypass -File `"$patchScript`" -PgPort $PgPort"

Write-Host "[6/7] Migration + restart API ..." -ForegroundColor Cyan
& powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "sync_deploy_fengji_api.ps1") `
    -SshAlias $SshAlias -RemoteRoot $RemoteRoot -RunMigration -RestartApi -Verify

if (-not $SkipAcceptance) {
    Write-Host "[7/7] W17 remote acceptance (no PG tunnel required) ..." -ForegroundColor Cyan
    python (Join-Path $PSScriptRoot "w17_remote_acceptance.py") --ssh-tunnel $SshAlias --local-port $AcceptanceLocalPort --wait-seconds 8
} else {
    Write-Host "[7/7] Skip acceptance (-SkipAcceptance)" -ForegroundColor DarkGray
}

Write-Host "`nP2 bootstrap finished. You may stop start_pg_reverse_tunnel.ps1 — API should use server PG on $PgPort." -ForegroundColor Green
