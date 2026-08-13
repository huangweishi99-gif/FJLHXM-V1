# Shadow 6/30 正式复评 · 一键收集
param(
    [string]$ReviewDir = ""
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

$stamp = Get-Date -Format "yyyyMMdd"
if (-not $ReviewDir) {
    $ReviewDir = Join-Path $root "results\shadow_observation_630_review_$stamp"
}
New-Item -ItemType Directory -Force -Path $ReviewDir | Out-Null

Write-Host "=== shadow reports ===" -ForegroundColor Cyan
python (Join-Path $root "scripts\report_paper_shadow_comparison.py") --json `
    | Tee-Object -FilePath (Join-Path $ReviewDir "shadow_reports.json")

Write-Host "=== ops shadow630 ===" -ForegroundColor Cyan
& (Join-Path $root "scripts\run_ops_round_check.ps1") -RoundTag shadow630 | Out-Null
$opsSrc = Join-Path $root "results\ops_round_${stamp}_shadow630"
if (Test-Path $opsSrc) {
    Copy-Item -Recurse -Force $opsSrc (Join-Path $ReviewDir "ops_snapshot")
}

Write-Host "=== domestic health ===" -ForegroundColor Cyan
& (Join-Path $root "scripts\check_domestic_main_contract_health.ps1") -Remote `
    2>&1 | Out-File -Encoding utf8 (Join-Path $ReviewDir "domestic_main_contract_health.txt")

Write-Host "=== domestic fill 72h ===" -ForegroundColor Cyan
ssh -o BatchMode=yes domestic-quant "powershell -NoProfile -ExecutionPolicy Bypass -File C:/Users/Administrator/quant_futures/scripts/_tmp_domestic_fill_verify_20260625.ps1" `
    2>&1 | Tee-Object -FilePath (Join-Path $ReviewDir "domestic_fill_verify.txt")

Write-Host "=== overseas fill 72h ===" -ForegroundColor Cyan
$overseasFillCmd = "cd /home/ubuntu/quant_crypto && export PYTHONPATH=src:packages/fengji_core && .venv/bin/python scripts/audit_paper_fills.py --root /home/ubuntu/quant_crypto --profile overseas --since-hours 72 --fail-on-invalid --ack-file runtime/fill_supervision_acknowledged.json --exec-gap-file runtime/fill_exec_gap_acknowledged.json --quiet && echo OVERSEAS_FILL_AUDIT_72H_EXIT=0 || echo OVERSEAS_FILL_AUDIT_72H_EXIT=2"
ssh -o BatchMode=yes overseas-quant $overseasFillCmd `
    2>&1 | Tee-Object -FilePath (Join-Path $ReviewDir "overseas_fill_verify.txt")

Write-Host "review_dir=$ReviewDir" -ForegroundColor Green
Write-Host "See SUMMARY.md + USER_DECISION.md in review folder (update manually if first run)." -ForegroundColor DarkGray
