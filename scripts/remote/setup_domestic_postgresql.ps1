# Install/configure PostgreSQL on domestic-quant (server-side). Idempotent.
# Requires Administrator. Secrets stay server-local; do not commit passwords.
param(
    [string]$Root = "C:\Users\Administrator\quant_futures",
    [int]$PgPort = 5432,
    [string]$PgUser = "fengji",
    [string]$PgDatabase = "fengji",
    [string]$InstallerUrl = "https://get.enterprisedb.com/postgresql/postgresql-16.6-1-windows-x64.exe",
    [string]$InstallerPath = "",
    [switch]$Install,
    [switch]$SkipCreateUser,
    [string]$DumpPath = ""
)

$ErrorActionPreference = "Stop"

function Find-Psql {
    $preferred = @(
        "C:\Program Files\PostgreSQL\16\bin\psql.exe",
        "C:\Program Files\PostgreSQL\15\bin\psql.exe"
    )
    foreach ($p in $preferred) {
        if (Test-Path -LiteralPath $p) { return $p }
    }
    $cmd = Get-Command psql -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $roots = @(
        "C:\Program Files\PostgreSQL",
        "C:\Program Files (x86)\PostgreSQL"
    )
    foreach ($base in $roots) {
        if (-not (Test-Path -LiteralPath $base)) { continue }
        $hit = Get-ChildItem -Path $base -Recurse -Filter psql.exe -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending |
            Select-Object -First 1
        if ($hit) { return $hit.FullName }
    }
    return $null
}

function Test-PgReady {
    param([string]$PsqlPath, [string]$User, [string]$Db)
    if (-not $PsqlPath) { return $false }
    $env:PGPASSWORD = $env:FENGJI_PG_PASSWORD
    & $PsqlPath -h 127.0.0.1 -p $PgPort -U $User -d $Db -c "SELECT 1" 2>$null | Out-Null
    return $LASTEXITCODE -eq 0
}

function Ensure-PgPassword {
    if ($env:FENGJI_PG_PASSWORD) { return }
    $secretDir = Join-Path $Root "runtime\secrets"
    New-Item -ItemType Directory -Force -Path $secretDir | Out-Null
    $pwFile = Join-Path $secretDir "fengji_pg_password.txt"
    if (Test-Path -LiteralPath $pwFile) {
        $env:FENGJI_PG_PASSWORD = (Get-Content -LiteralPath $pwFile -Raw).Trim()
        return
    }
    $bytes = New-Object byte[] 24
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $env:FENGJI_PG_PASSWORD = [Convert]::ToBase64String($bytes) -replace '[+/=]', 'x'
    Set-Content -LiteralPath $pwFile -Value $env:FENGJI_PG_PASSWORD -Encoding UTF8 -NoNewline
    Write-Host "Generated server-local PG password file: runtime/secrets/fengji_pg_password.txt"
}

function Tune-PostgresLowMemory {
    param([string]$Root, [int]$PgPort)
    $dataRoot = "C:\Program Files\PostgreSQL"
    if (-not (Test-Path -LiteralPath $dataRoot)) { return }
    $conf = Get-ChildItem -Path $dataRoot -Recurse -Filter postgresql.conf -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match "\\data\\postgresql\.conf$" } |
        Select-Object -First 1
    if (-not $conf) { return }
    $text = Get-Content -LiteralPath $conf.FullName -Raw -Encoding UTF8
    if ($text -match "fengji low-memory tune") { return }
    $block = @"

# fengji low-memory tune (2c4g host)
shared_buffers = 128MB
max_connections = 30
work_mem = 4MB
maintenance_work_mem = 64MB
effective_cache_size = 512MB
"@
    Add-Content -LiteralPath $conf.FullName -Value $block -Encoding UTF8
    Restart-Service -Name "postgresql-x64-16" -ErrorAction SilentlyContinue
    Write-Host "Tuned postgresql.conf for low-memory host."
}

Ensure-PgPassword
$pgPassword = $env:FENGJI_PG_PASSWORD
if (-not $pgPassword) { throw "FENGJI_PG_PASSWORD empty" }

$listening = Get-NetTCPConnection -LocalPort $PgPort -State Listen -ErrorAction SilentlyContinue
if ($listening) {
    Write-Host "Port $PgPort already listening — skip installer." -ForegroundColor Green
} elseif ($Install) {
    $tempDir = Join-Path $env:TEMP "fengji_pg_install"
    New-Item -ItemType Directory -Force -Path $tempDir | Out-Null
    if ($InstallerPath -and (Test-Path -LiteralPath $InstallerPath)) {
        $installer = $InstallerPath
        Write-Host "Using local installer: $installer"
    } else {
        $installer = Join-Path $tempDir "postgresql-installer.exe"
        if (-not (Test-Path -LiteralPath $installer)) {
            Write-Host "Downloading PostgreSQL installer ..."
            try {
                [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
                Invoke-WebRequest -Uri $InstallerUrl -OutFile $installer -UseBasicParsing
            } catch {
                Write-Error "Download failed ($($_.Exception.Message)). SCP installer to server and pass -InstallerPath, or install PG manually."
                exit 1
            }
        }
    }
    if (-not $env:FENGJI_PG_SUPER_PASSWORD) {
        $bytes = New-Object byte[] 24
        [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
        $env:FENGJI_PG_SUPER_PASSWORD = [Convert]::ToBase64String($bytes) -replace '[+/=]', 'x'
        $superFile = Join-Path (Join-Path $Root "runtime\secrets") "postgres_super_password.txt"
        Set-Content -LiteralPath $superFile -Value $env:FENGJI_PG_SUPER_PASSWORD -Encoding UTF8 -NoNewline
        Write-Host "Saved postgres super password to runtime/secrets/postgres_super_password.txt"
    }
    $super = $env:FENGJI_PG_SUPER_PASSWORD
    $workTemp = Join-Path $Root "runtime\temp"
    New-Item -ItemType Directory -Force -Path $workTemp | Out-Null
    $env:TEMP = $workTemp
    $env:TMP = $workTemp
    $fixTemp = Join-Path $Root "scripts\remote\fix_server_temp_for_pg_install.ps1"
    if (Test-Path -LiteralPath $fixTemp) {
        & powershell -NoProfile -ExecutionPolicy Bypass -File $fixTemp -Root $Root
    }
    $preflight = Join-Path $Root "scripts\remote\preflight_pg_install_resources.ps1"
    if (Test-Path -LiteralPath $preflight) {
        & powershell -NoProfile -ExecutionPolicy Bypass -File $preflight -Root $Root
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    Write-Host "Running unattended PostgreSQL install via scheduled task (TEMP=$workTemp, may take 10-15 min) ..."
    $taskInstaller = Join-Path $Root "scripts\remote\install_postgresql_via_task.ps1"
    if (Test-Path -LiteralPath $taskInstaller) {
        & powershell -NoProfile -ExecutionPolicy Bypass -File $taskInstaller `
            -InstallerPath $installer -SuperPassword $super -PgPort $PgPort -Root $Root
        if ($LASTEXITCODE -ne 0) { throw "PostgreSQL installer exit code $LASTEXITCODE" }
    } else {
        $logDir = Join-Path $Root "runtime\logs"
        New-Item -ItemType Directory -Force -Path $logDir | Out-Null
        $installLog = Join-Path $logDir "pg_install_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"
        $args = @(
            "--mode", "unattended",
            "--unattendedmodeui", "none",
            "--superpassword", $super,
            "--servicename", "postgresql-x64-16",
            "--servicepassword", $super,
            "--serverport", "$PgPort"
        )
        $env:ComSpec = "$env:SystemRoot\System32\cmd.exe"
        $env:COMSPEC = $env:ComSpec
        $proc = Start-Process -FilePath $installer -ArgumentList $args -PassThru -NoNewWindow -WorkingDirectory $workTemp -RedirectStandardOutput $installLog -RedirectStandardError ($installLog + ".err")
        try { $proc.PriorityClass = [System.Diagnostics.ProcessPriorityClass]::BelowNormal } catch { }
        $proc.WaitForExit()
        if ($proc.ExitCode -ne 0) {
            if (Test-Path -LiteralPath $installLog) { Get-Content -LiteralPath $installLog -Tail 20 }
            throw "PostgreSQL installer exit code $($proc.ExitCode)"
        }
    }
    Start-Sleep -Seconds 8
    Tune-PostgresLowMemory -Root $Root -PgPort $PgPort
} else {
    throw "Port $PgPort not listening. Re-run with -Install (Administrator required)."
}

$psql = Find-Psql
if (-not $psql) { throw "psql.exe not found after install" }
Write-Host "Using psql: $psql"

$superPassword = $env:FENGJI_PG_SUPER_PASSWORD
if (-not $superPassword) {
    $superFile = Join-Path (Join-Path $Root "runtime\secrets") "postgres_super_password.txt"
    if (Test-Path -LiteralPath $superFile) {
        $superPassword = (Get-Content -LiteralPath $superFile -Raw).Trim()
    }
}

if (-not $SkipCreateUser) {
    $env:PGPASSWORD = $superPassword
    $roleExists = & $psql -h 127.0.0.1 -p $PgPort -U postgres -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='$PgUser'" 2>$null
    if ($roleExists -ne "1") {
        & $psql -h 127.0.0.1 -p $PgPort -U postgres -d postgres -c "CREATE ROLE $PgUser LOGIN PASSWORD '$pgPassword';"
    } else {
        & $psql -h 127.0.0.1 -p $PgPort -U postgres -d postgres -c "ALTER ROLE $PgUser WITH PASSWORD '$pgPassword';"
    }
    $dbExists = & $psql -h 127.0.0.1 -p $PgPort -U postgres -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$PgDatabase'" 2>$null
    if ($dbExists -ne "1") {
        & $psql -h 127.0.0.1 -p $PgPort -U postgres -d postgres -c "CREATE DATABASE $PgDatabase OWNER $PgUser;"
    } else {
        & $psql -h 127.0.0.1 -p $PgPort -U postgres -d postgres -c "ALTER DATABASE $PgDatabase OWNER TO $PgUser;"
    }
    Write-Host "Database user/db ready: $PgUser@127.0.0.1:$PgPort/$PgDatabase" -ForegroundColor Green
}

if (-not (Test-PgReady -PsqlPath $psql -User $PgUser -Db $PgDatabase)) {
    throw "PG ready check failed for $PgUser@127.0.0.1:$PgPort/$PgDatabase"
}

if ($DumpPath -and (Test-Path -LiteralPath $DumpPath)) {
    $pgRestore = Join-Path (Split-Path $psql -Parent) "pg_restore.exe"
    if (-not (Test-Path -LiteralPath $pgRestore)) { throw "pg_restore not found next to psql" }
    Write-Host "Restoring dump (clean) ..."
    $env:PGPASSWORD = $pgPassword
    & $pgRestore -h 127.0.0.1 -p $PgPort -U $PgUser -d $PgDatabase --clean --if-exists --no-owner --no-privileges $DumpPath
    if ($LASTEXITCODE -ne 0) {
        Write-Host "pg_restore exit $LASTEXITCODE — schema may be empty; alembic upgrade will continue." -ForegroundColor Yellow
    }
}

Write-Host "PostgreSQL setup OK on 127.0.0.1:$PgPort" -ForegroundColor Green
