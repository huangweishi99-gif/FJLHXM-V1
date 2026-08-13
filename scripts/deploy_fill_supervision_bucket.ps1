# fill_supervision + ds03_pending_fill 桶（本地 HEAD 为准，对齐海内外 hash）
param(
    [switch]$OverseasOnly,
    [switch]$DomesticOnly,
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

$files = @(
    "packages/fengji_core/fengji_core/fill_supervision.py",
    "packages/fengji_core/fengji_core/ds03_pending_fill.py"
)

if (-not $SkipTests) {
    Write-Host "=== pytest ===" -ForegroundColor Cyan
    python -m pytest (Join-Path $root "tests\test_fill_supervision.py") (Join-Path $root "tests\test_ds03_pending_fill.py") (Join-Path $root "tests\test_feishu_notify.py") -q
    if ($LASTEXITCODE -ne 0) { throw "pytest failed" }
}

function Sync-List([string]$HostAlias, [string]$RemoteRoot, [string[]]$Paths) {
    foreach ($rel in $Paths) {
        $local = Join-Path $root ($rel -replace "/", "\")
        if (-not (Test-Path -LiteralPath $local)) { throw "missing: $local" }
        $remote = "$RemoteRoot/$($rel -replace '\\','/')"
        scp -o BatchMode=yes -o ConnectTimeout=25 $local "${HostAlias}:$remote"
        if ($LASTEXITCODE -ne 0) { throw "scp failed: $rel -> $HostAlias" }
        Write-Host "synced ${HostAlias}: $rel"
    }
}

if (-not $DomesticOnly) {
    Write-Host "=== Overseas ===" -ForegroundColor Cyan
    Sync-List "overseas-quant" "/home/ubuntu/quant_crypto" $files
}

if (-not $OverseasOnly) {
    Write-Host "=== Domestic ===" -ForegroundColor Cyan
    Sync-List "domestic-quant" "C:/Users/Administrator/quant_futures" $files
}

if (-not $DomesticOnly) {
    Write-Host "=== overseas hash ===" -ForegroundColor Cyan
    python (Join-Path $root "scripts\compare_overseas_core_hashes.py")
    $rows = python (Join-Path $root "scripts\compare_overseas_core_hashes.py") | ConvertFrom-Json
    foreach ($name in @("fill_supervision.py", "ds03_pending_fill.py")) {
        $row = $rows.rows | Where-Object { $_.file -like "*$name" } | Select-Object -First 1
        if ($row -and -not $row.match) {
            Write-Warning "hash still mismatched: $($row.file)"
        }
    }
}

Write-Host "=== Done ===" -ForegroundColor Green
