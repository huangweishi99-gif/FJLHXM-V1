param(
    [string]$TargetDir = "C:\Users\Administrator\quant_futures"
)

$ErrorActionPreference = "Stop"

$PackageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupDir = Join-Path $TargetDir "backup_ds07_$Stamp"

$Files = @(
    @{ Source = "src\quant\ds07.py"; Target = "src\quant\ds07.py" },
    @{ Source = "src\backtest_ds07.py"; Target = "src\backtest_ds07.py" },
    @{ Source = "src\plot_ds07_sandbox.py"; Target = "src\plot_ds07_sandbox.py" }
)

if (-not (Test-Path $TargetDir)) {
    throw "Target folder not found: $TargetDir"
}

Write-Host "Target: $TargetDir"
Write-Host "Package: $PackageRoot"
Write-Host "Backup: $BackupDir"

New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

foreach ($item in $Files) {
    $source = Join-Path $PackageRoot $item.Source
    $target = Join-Path $TargetDir $item.Target

    if (-not (Test-Path $source)) {
        throw "Package file missing: $source"
    }
    if (-not (Test-Path $target)) {
        throw "Target file missing, stop to avoid wrong folder: $target"
    }

    $backupPath = Join-Path $BackupDir $item.Target
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $backupPath) | Out-Null
    Copy-Item -LiteralPath $target -Destination $backupPath -Force
    Copy-Item -LiteralPath $source -Destination $target -Force

    Write-Host "Updated: $($item.Target)"
}

$ds07Path = Join-Path $TargetDir "src\quant\ds07.py"
$ds07Text = Get-Content -LiteralPath $ds07Path -Raw
$requiredMarkers = @(
    "LONG_ALIGN_TURN",
    "LONG_CONTINUE",
    "SHORT_ALIGN_TURN",
    "SHORT_CONTINUE",
    "prev_h1_camp",
    "hardened_count"
)

$missingMarkers = @()
foreach ($marker in $requiredMarkers) {
    if ($ds07Text -notmatch [regex]::Escape($marker)) {
        $missingMarkers += $marker
    }
}

if ($missingMarkers.Count -gt 0) {
    throw "DS07 marker check failed. Missing: $($missingMarkers -join ', ')"
}

Write-Host "DS07 marker check OK."

$python = $null
try {
    $python = (Get-Command python -ErrorAction Stop).Source
} catch {
    try {
        $python = (Get-Command py -ErrorAction Stop).Source
    } catch {
        $python = $null
    }
}

if ($python) {
    Push-Location $TargetDir
    try {
        if ((Split-Path -Leaf $python) -eq "py.exe") {
            & $python -3 -m py_compile "src\quant\ds07.py" "src\backtest_ds07.py" "src\plot_ds07_sandbox.py"
        } else {
            & $python -m py_compile "src\quant\ds07.py" "src\backtest_ds07.py" "src\plot_ds07_sandbox.py"
        }
        Write-Host "Python compile check OK."
    } finally {
        Pop-Location
    }
} else {
    Write-Host "Python command not found; skipped compile check."
}

$shellFiles = @(
    "峰极总定式01-08国内期货模拟实盘.py",
    "data_manager_futures.py",
    "商业终端_Dash.py"
)

foreach ($name in $shellFiles) {
    $path = Join-Path $TargetDir $name
    if (Test-Path $path) {
        Write-Host "Kept unchanged: $name"
    } else {
        Write-Host "Not found in target: $name"
    }
}

Write-Host ""
Write-Host "Done. Only DS07 strategy files were updated. Domestic futures trading rules were not changed."
Write-Host "Backup folder: $BackupDir"
