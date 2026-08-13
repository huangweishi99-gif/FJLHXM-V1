# Complete N04 OS state swap + fill audit + restart when rebuild already finished.
param(
    [Parameter(Mandatory = $true)]
    [string]$RebuildDir,
    [ValidateSet("domestic", "overseas", "local")]
    [string]$Profile = "domestic",
    [string]$BackupDir = "",
    [string]$AuditDir = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$env:PYTHONPATH = "$Root/src;$Root/packages/fengji_core"

$stateRoot = Join-Path $Root "runtime/fengji_os_state"
if (-not (Test-Path $RebuildDir)) { throw "rebuild dir missing: $RebuildDir" }
if (-not $BackupDir) {
    $parent = Split-Path $RebuildDir -Parent
    $name = Split-Path $RebuildDir -Leaf
    if ($name -match "_rebuild_(.+)$") {
        $BackupDir = Join-Path $parent ("fengji_os_state_backup_" + $Matches[1])
    }
}
if (-not $AuditDir) {
    $AuditDir = Join-Path $Root ("results/os_state_rebuild/" + $Profile + "_complete")
}

Write-Host "[1/4] swap state -> $stateRoot" -ForegroundColor Cyan
Remove-Item -LiteralPath $stateRoot -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item -LiteralPath $RebuildDir -Destination $stateRoot -Recurse
Write-Host "SWAPPED from $RebuildDir"

Write-Host "[2/4] diff (if backup exists) ..." -ForegroundColor Cyan
if ($BackupDir -and (Test-Path $BackupDir)) {
    python scripts/audit_os_state_rebuild_impact.py `
        --before-dir $BackupDir `
        --after-dir $RebuildDir `
        --out-dir $AuditDir `
        --label $Profile
}

Write-Host "[3/4] fill supervision re-audit ..." -ForegroundColor Cyan
$fillProfile = if ($Profile -eq "domestic") { "domestic" } elseif ($Profile -eq "overseas") { "overseas" } else { "" }
if ($fillProfile) {
    python scripts/audit_paper_fills.py --profile $fillProfile --since-hours 720 --out-dir (Join-Path $AuditDir "fill_supervision") --quiet
    Write-Host "fill_audit_exit=$LASTEXITCODE (non-zero invalid fills expected; not blocking swap)"
}

Write-Host "[4/4] restart runtime ..." -ForegroundColor Cyan
if ($Profile -eq "domestic") {
    & (Join-Path $Root "scripts/restart_domestic_futures_runtime.ps1")
} elseif ($Profile -eq "overseas") {
    throw "Use bash restart_overseas_runtime.sh on overseas host"
}

Write-Host "Complete swap done ($Profile)." -ForegroundColor Green
