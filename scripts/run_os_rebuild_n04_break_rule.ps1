# Rebuild FengJi OS state after N04 break-rule + C-class defense fallback (2026-06-10).
param(
    [string]$Root = "",
    [ValidateSet("domestic", "overseas", "local")]
    [string]$Profile = "local",
    [switch]$SkipRestart,
    [switch]$SkipFillAudit,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
if (-not $Root) {
    $Root = Split-Path -Parent $PSScriptRoot
}
Set-Location $Root

$env:PYTHONPATH = "$Root/src;$Root/packages/fengji_core"
if ($Profile -eq "domestic") {
    $env:FENGJI_MARKET = "futures"
    $inputs = @(
        "--input", "data/1d,market=futures",
        "--input", "data/1h,market=futures",
        "--input", "data/15m,market=futures"
    )
    $fillProfile = "domestic"
    $stopScript = Join-Path $Root "scripts/stop_domestic_futures_runtime.ps1"
    $restartScript = Join-Path $Root "scripts/restart_domestic_futures_runtime.ps1"
} elseif ($Profile -eq "overseas") {
    $env:FENGJI_MARKET = "crypto"
    $inputs = @(
        "--input", "data/1d,market=crypto",
        "--input", "data/1h,market=crypto",
        "--input", "data/15m,market=crypto"
    )
    $fillProfile = "overseas"
    $stopScript = ""
    $restartScript = ""
} else {
    $env:FENGJI_MARKET = "crypto"
    $inputs = @()
    foreach ($spec in @(
        @{ Path = "data/1d"; Market = "crypto" },
        @{ Path = "data/1h"; Market = "crypto" },
        @{ Path = "data/15m"; Market = "crypto" },
        @{ Path = "data/1d"; Market = "futures" },
        @{ Path = "data/1h"; Market = "futures" },
        @{ Path = "data/15m"; Market = "futures" }
    )) {
        if (Test-Path (Join-Path $Root $spec.Path)) {
            $inputs += @("--input", "$($spec.Path),market=$($spec.Market)")
        }
    }
    if (-not $inputs) {
        throw "No data/1d|1h|15m directories found under $Root"
    }
    $fillProfile = ""
    $stopScript = ""
    $restartScript = ""
}

Write-Host "[1/8] verify os_engine N04 ..." -ForegroundColor Cyan
python scripts/verify_os_engine_n04.py
if ($LASTEXITCODE -ne 0) { throw "os_engine N04 verification failed" }

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$stateRoot = Join-Path $Root "runtime/fengji_os_state"
$backup = Join-Path $Root "runtime/fengji_os_state_backup_$stamp"
$rebuild = Join-Path $Root "runtime/fengji_os_state_rebuild_$stamp"
$auditDir = Join-Path $Root "results/os_state_rebuild/$Profile`_$stamp"

if (-not (Test-Path $stateRoot)) {
    New-Item -ItemType Directory -Force -Path $stateRoot | Out-Null
}

Write-Host "[2/8] stop runtime (if script exists) ..." -ForegroundColor Cyan
if ($stopScript -and (Test-Path $stopScript) -and -not $DryRun) {
    & $stopScript
    Start-Sleep -Seconds 2
} else {
    Write-Host "  skip stop (profile=$Profile dryRun=$DryRun)" -ForegroundColor DarkGray
}

Write-Host "[3/8] backup current state -> $backup" -ForegroundColor Cyan
if (-not $DryRun) {
    Copy-Item -LiteralPath $stateRoot -Destination $backup -Recurse -Force
}

Write-Host "[4/8] rebuild all D1/H1/15m states -> $rebuild" -ForegroundColor Cyan
$rebuildArgs = @(
    "scripts/rebuild_os_state_all.py",
    "--state-dir", $rebuild,
    "--audit-dir", $auditDir,
    "--mode", "rebuild"
) + $inputs
if ($DryRun) {
    Write-Host "  DRY RUN rebuild command: python $($rebuildArgs -join ' ')" -ForegroundColor Yellow
} else {
    python @rebuildArgs
    if ($LASTEXITCODE -ne 0) { throw "rebuild_os_state_all failed" }
}

Write-Host "[5/8] diff before/after state ..." -ForegroundColor Cyan
if (-not $DryRun) {
    python scripts/audit_os_state_rebuild_impact.py `
        --before-dir $backup `
        --after-dir $rebuild `
        --out-dir $auditDir `
        --label $Profile
    if ($LASTEXITCODE -ne 0) { throw "audit_os_state_rebuild_impact failed" }
}

Write-Host "[6/8] fill supervision re-audit (720h) ..." -ForegroundColor Cyan
if (-not $SkipFillAudit -and $fillProfile -and -not $DryRun) {
    python scripts/audit_os_state_rebuild_impact.py `
        --before-dir $backup `
        --after-dir $rebuild `
        --out-dir $auditDir `
        --label $Profile `
        --fill-audit-profile $fillProfile
    Write-Host "fill_audit_exit=$LASTEXITCODE (invalid fills may remain; review report, not blocking swap)" -ForegroundColor Yellow
} else {
    Write-Host "  skip fill audit (profile=$fillProfile skip=$SkipFillAudit dryRun=$DryRun)" -ForegroundColor DarkGray
}

Write-Host "[7/8] swap rebuilt state into runtime/fengji_os_state ..." -ForegroundColor Cyan
if (-not $DryRun) {
    Remove-Item -LiteralPath $stateRoot -Recurse -Force
    Copy-Item -LiteralPath $rebuild -Destination $stateRoot -Recurse
    Write-Host "SWAPPED_TO=$rebuild BACKUP=$backup AUDIT=$auditDir"
}

Write-Host "[8/8] restart runtime ..." -ForegroundColor Cyan
if ($restartScript -and (Test-Path $restartScript) -and -not $SkipRestart -and -not $DryRun) {
    & $restartScript
} else {
    Write-Host "  skip restart (profile=$Profile skipRestart=$SkipRestart dryRun=$DryRun)" -ForegroundColor DarkGray
}

Write-Host "`nOS state N04 rebuild complete ($Profile)." -ForegroundColor Green
