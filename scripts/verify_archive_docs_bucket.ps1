# Archive docs bucket verification (2026-06-02 results batches; no zip commit).
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

Write-Host "=== archive manifest test ===" -ForegroundColor Cyan
python -m pytest tests/test_fengji_archive_manifest.py -q
if ($LASTEXITCODE -ne 0) { throw "archive manifest pytest failed" }

Write-Host "=== archive CSV row counts ===" -ForegroundColor Cyan
foreach ($batch in @("phase1", "phase2")) {
    $manifest = Join-Path $root "archives\2026-06-02_results_$batch\manifest.csv"
    if (-not (Test-Path -LiteralPath $manifest)) { throw "missing $manifest" }
    $rows = (Import-Csv -LiteralPath $manifest).Count
    Write-Host "$batch manifest rows=$rows"
}

Write-Host "=== Archive docs bucket OK ===" -ForegroundColor Green
