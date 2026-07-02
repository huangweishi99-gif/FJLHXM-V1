# Grant fengji app role access to public schema (after pg_restore as postgres).
param(
    [string]$Root = "C:\Users\Administrator\quant_futures",
    [string]$DbName = "fengji",
    [string]$DbUser = "fengji",
    [int]$Port = 5432
)

$ErrorActionPreference = "Stop"
$secretDir = Join-Path $Root "runtime\secrets"
$candidates = @(
    (Join-Path $secretDir "pg_super.secret"),
    (Join-Path $secretDir "postgres_super_password.txt")
)
$secretFile = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $secretFile) { throw "Missing postgres super password file" }
$superPwd = (Get-Content -LiteralPath $secretFile -Raw).Trim()

$pgRestore = @(
    "C:\Program Files\PostgreSQL\16\bin\pg_restore.exe",
    "C:\Program Files\PostgreSQL\15\bin\pg_restore.exe"
) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
$psql = $pgRestore -replace "pg_restore.exe", "psql.exe"
if (-not (Test-Path -LiteralPath $psql)) {
    $cmd = Get-Command psql.exe -ErrorAction SilentlyContinue
    if ($cmd) { $psql = $cmd.Source }
}
if (-not (Test-Path -LiteralPath $psql)) { throw "psql.exe not found" }

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
Write-Host "Granted public schema privileges to $DbUser"
