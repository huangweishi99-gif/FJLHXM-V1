# W17-prod: sync FengJi Web API (services + migrations + deploy scripts) to domestic server.
# Does NOT sync secrets, JWT keys, or payment redeem codes.
# Does NOT restart paper/radar/data_manager unless -RestartApi is set.
param(
    [Alias("Remote")]
    [string]$SshAlias = "domestic-quant",
    [string]$RemoteRoot = "C:\Users\Administrator\quant_futures",
    [switch]$SyncWeb,
    [switch]$RunMigration,
    [switch]$RestartApi,
    [switch]$InstallTask,
    [switch]$Verify
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Manifest = Join-Path $PSScriptRoot "fengji_api_deploy_manifest.txt"

function ConvertTo-RemoteWindowsPath {
    param([string]$Path)
    return ($Path -replace "/", "\")
}

function ConvertTo-ScpRemotePath {
    param([string]$WinPath)
    $normalized = ($WinPath -replace "\\", "/").TrimEnd("/")
    if ($normalized -match '^([A-Za-z]):/(.*)$') {
        return "/$($Matches[1]):/$($Matches[2])"
    }
    if ($normalized -match '^([A-Za-z]):$') {
        return "/$($Matches[1]):/"
    }
    return $normalized
}

function Invoke-RemoteMkdir {
    param(
        [string]$RemoteHost,
        [string]$DirPath
    )
    $posixDir = (ConvertTo-RemoteWindowsPath $DirPath) -replace "\\", "/"
    $escaped = $posixDir -replace "'", "''"
    ssh -o BatchMode=yes $RemoteHost "powershell -NoProfile -Command ""New-Item -ItemType Directory -Force -Path '$escaped' | Out-Null"""
}

function Copy-RemoteFile {
    param(
        [string]$RemoteHost,
        [string]$LocalPath,
        [string]$RemotePath
    )
    $winRemote = ConvertTo-RemoteWindowsPath $RemotePath
    Invoke-RemoteMkdir -RemoteHost $RemoteHost -DirPath (Split-Path $winRemote -Parent)
    $scpRemote = ConvertTo-ScpRemotePath $winRemote
    $dest = "$RemoteHost`:$scpRemote"
    & scp -o BatchMode=yes $LocalPath $dest
    if ($LASTEXITCODE -ne 0) {
        throw "scp failed ($LASTEXITCODE): $LocalPath -> $dest"
    }
}

if (-not (Test-Path -LiteralPath $Manifest)) {
    throw "Missing manifest: $Manifest"
}

$files = Get-Content -LiteralPath $Manifest -Encoding UTF8 |
    ForEach-Object { $_.Trim() } |
    Where-Object { $_ -and -not $_.StartsWith("#") }

Write-Host "[1/4] sync API manifest ($($files.Count) files) -> $SshAlias ..." -ForegroundColor Cyan
foreach ($rel in $files) {
    $local = Join-Path $Root ($rel -replace "/", "\")
    if (-not (Test-Path -LiteralPath $local)) {
        throw "Missing local file: $local"
    }
    $remoteFile = Join-Path $RemoteRoot ($rel -replace "/", "\")
    Copy-RemoteFile -RemoteHost $SshAlias -LocalPath $local -RemotePath $remoteFile
    Write-Host "  OK $rel" -ForegroundColor DarkGray
}

if ($SyncWeb) {
    Write-Host "[2/4] sync web/ static frontend ..." -ForegroundColor Cyan
    $remoteWeb = Join-Path $RemoteRoot "web"
    Invoke-RemoteMkdir -RemoteHost $SshAlias -DirPath $remoteWeb
    $scpWebDir = ConvertTo-ScpRemotePath $remoteWeb
    $webDest = "$SshAlias`:$scpWebDir/"
    & scp -o BatchMode=yes -r (Join-Path $Root "web\*") $webDest
    if ($LASTEXITCODE -ne 0) {
        throw "scp web/ failed ($LASTEXITCODE)"
    }
    Write-Host "  OK web/" -ForegroundColor DarkGray
} else {
    Write-Host "[2/4] skip web/ (pass -SyncWeb to include frontend)" -ForegroundColor DarkGray
}

$remoteRootPosix = ($RemoteRoot -replace "\\", "/")
$remoteRootWin = ConvertTo-RemoteWindowsPath $RemoteRoot

if ($RunMigration) {
    Write-Host "[3/4] alembic upgrade head on remote ..." -ForegroundColor Cyan
    $migrateScript = Join-Path $remoteRootWin "scripts\run_alembic_upgrade.ps1"
    ssh -o BatchMode=yes $SshAlias "powershell -NoProfile -ExecutionPolicy Bypass -File `"$migrateScript`""
} else {
    Write-Host "[3/4] skip migration (pass -RunMigration after DATABASE_URL is configured on server)" -ForegroundColor DarkGray
}

if ($InstallTask) {
    Write-Host "[4/4] install scheduled task FengJiApiServer ..." -ForegroundColor Cyan
    ssh -o BatchMode=yes $SshAlias "powershell -NoProfile -ExecutionPolicy Bypass -File `"$($remoteRootWin)\scripts\install_fengji_api_task.ps1`""
} elseif ($RestartApi) {
    Write-Host "[4/4] restart API process ..." -ForegroundColor Cyan
    ssh -o BatchMode=yes $SshAlias "powershell -NoProfile -ExecutionPolicy Bypass -File `"$($remoteRootWin)\scripts\restart_fengji_api.ps1`""
} else {
    Write-Host "[4/4] skip API restart (pass -RestartApi or -InstallTask)" -ForegroundColor DarkGray
}

if ($Verify) {
    Write-Host "[verify] remote health check ..." -ForegroundColor Cyan
    ssh -o BatchMode=yes $SshAlias "powershell -NoProfile -ExecutionPolicy Bypass -File `"$($remoteRootWin)\scripts\verify_fengji_api_health.ps1`""
}

Write-Host "`nFengJi API deploy sync done." -ForegroundColor Green
Write-Host "Secrets: create $remoteRootWin\runtime\secrets\fengji_api.env on server (see scripts/remote_fengji_api_env.example.ps1)" -ForegroundColor Yellow
