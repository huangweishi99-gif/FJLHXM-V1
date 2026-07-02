# Build DATABASE_URL from server-local fengji_pg_password.txt and patch env (no JWT rotation).
param(
    [int]$PgPort = 5432,
    [string]$PgUser = "fengji",
    [string]$PgDatabase = "fengji",
    [string]$Root = "C:\Users\Administrator\quant_futures"
)

$ErrorActionPreference = "Stop"
$pwFile = Join-Path $Root "runtime\secrets\fengji_pg_password.txt"
if (Test-Path -LiteralPath $pwFile) {
    $pw = (Get-Content -LiteralPath $pwFile -Raw).Trim()
} else {
    $pw = "fengji_dev"
    Write-Host "No fengji_pg_password.txt — using default dev password for bootstrap."
}
$encPw = [uri]::EscapeDataString($pw)
$dbUrl = "postgresql+psycopg://${PgUser}:${encPw}@127.0.0.1:${PgPort}/${PgDatabase}"
$patch = Join-Path $Root "scripts\remote\patch_fengji_api_env.ps1"
& powershell -NoProfile -ExecutionPolicy Bypass -File $patch -DatabaseUrl $dbUrl -Root $Root
