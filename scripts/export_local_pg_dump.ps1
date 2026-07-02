# Dump local Docker PostgreSQL (fengji_pg) for remote restore (W17 P2).
param(
    [string]$OutDir = "",
    [string]$Container = "fengji_pg"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not $OutDir) {
    $OutDir = Join-Path $Root "runtime\backups\pg_export"
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$remoteDump = "/tmp/fengji_$stamp.dump"
$localDump = Join-Path $OutDir "fengji_$stamp.dump"

$ready = docker exec $Container pg_isready -U fengji -d fengji 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "Container $Container not ready. Start: docker compose up -d"
}

docker exec $Container pg_dump -U fengji -d fengji -Fc -f $remoteDump
if ($LASTEXITCODE -ne 0) { throw "pg_dump failed" }
docker cp "${Container}:${remoteDump}" $localDump
docker exec $Container rm -f $remoteDump | Out-Null

Write-Host "Dump: $localDump"
Write-Host $localDump
