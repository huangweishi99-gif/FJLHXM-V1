# Write server-local fengji PG app password (not printed).
param(
    [Parameter(Mandatory = $true)]
    [string]$Password,
    [string]$Root = "C:\Users\Administrator\quant_futures"
)

$ErrorActionPreference = "Stop"
$secretDir = Join-Path $Root "runtime\secrets"
New-Item -ItemType Directory -Force -Path $secretDir | Out-Null
$pwFile = Join-Path $secretDir "fengji_pg_password.txt"
Set-Content -LiteralPath $pwFile -Value $Password -Encoding UTF8 -NoNewline
Write-Host "Updated runtime/secrets/fengji_pg_password.txt"
