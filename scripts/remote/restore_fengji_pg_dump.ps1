# Restore pg_dump custom-format backup into local PostgreSQL (server-side).
param(
    [Parameter(Mandatory = $true)]
    [string]$DumpPath,
    [string]$DbName = "fengji",
    [string]$DbUser = "fengji",
    [int]$Port = 5432,
    [string]$Root = "C:\Users\Administrator\quant_futures"
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $DumpPath)) {
    throw "Dump not found: $DumpPath"
}

$secretDir = Join-Path $Root "runtime\secrets"
$candidates = @(
    (Join-Path $secretDir "pg_super.secret"),
    (Join-Path $secretDir "postgres_super_password.txt")
)
$secretFile = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $secretFile) {
    throw "Missing postgres super password file — expected one of: $($candidates -join ', ')"
}
$superPwd = (Get-Content -LiteralPath $secretFile -Raw).Trim()

$pgRestore = @(
    "C:\Program Files\PostgreSQL\16\bin\pg_restore.exe",
    "C:\Program Files\PostgreSQL\15\bin\pg_restore.exe"
) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $pgRestore) {
    $cmd = Get-Command pg_restore.exe -ErrorAction SilentlyContinue
    if ($cmd) { $pgRestore = $cmd.Source }
}
if (-not $pgRestore) { throw "pg_restore.exe not found" }

$psql = $pgRestore -replace "pg_restore.exe", "psql.exe"
$env:PGPASSWORD = $superPwd
& $psql -h 127.0.0.1 -p $Port -U postgres -d postgres -v ON_ERROR_STOP=1 -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$DbName' AND pid <> pg_backend_pid();" 2>$null | Out-Null
& $psql -h 127.0.0.1 -p $Port -U postgres -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS $DbName;"
& $psql -h 127.0.0.1 -p $Port -U postgres -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE $DbName OWNER $DbUser;"
Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue

$env:PGPASSWORD = $superPwd
& $pgRestore -h 127.0.0.1 -p $Port -U postgres -d $DbName --no-owner --no-acl $DumpPath
$code = $LASTEXITCODE
Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
if ($code -ne 0) {
    Write-Host "pg_restore exit $code (non-fatal warnings are common)" -ForegroundColor Yellow
}

Write-Host "Granting app role privileges on public schema ..."
$grantSql = @"
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $DbUser;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $DbUser;
GRANT USAGE ON SCHEMA public TO $DbUser;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $DbUser;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $DbUser;
"@
$env:PGPASSWORD = $superPwd
& $psql -h 127.0.0.1 -p $Port -U postgres -d $DbName -v ON_ERROR_STOP=1 -c $grantSql
Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue

Write-Host "restore_fengji_pg_dump.ps1 finished"
