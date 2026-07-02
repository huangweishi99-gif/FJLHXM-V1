# Run on server via RDP after manual PostgreSQL install (password not printed).
param(
    [string]$Root = "C:\Users\Administrator\quant_futures"
)

$ErrorActionPreference = "Stop"
$secretDir = Join-Path $Root "runtime\secrets"
New-Item -ItemType Directory -Force -Path $secretDir | Out-Null
$pwFile = Join-Path $secretDir "postgres_super_password.txt"

Write-Host "Enter the postgres superuser password you set in the installer:"
$sec = Read-Host -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
try {
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
}
if (-not $plain) { throw "Empty password" }
Set-Content -LiteralPath $pwFile -Value $plain -Encoding UTF8 -NoNewline

# verify
$psql = "C:\Program Files\PostgreSQL\16\bin\psql.exe"
if (-not (Test-Path -LiteralPath $psql)) {
    $psql = (Get-Command psql -ErrorAction SilentlyContinue).Source
}
$env:PGPASSWORD = $plain
& $psql -h 127.0.0.1 -p 5432 -U postgres -d postgres -c "SELECT 1" 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Password verify failed — check password and retry" }
Write-Host "Saved and verified: runtime/secrets/postgres_super_password.txt"
