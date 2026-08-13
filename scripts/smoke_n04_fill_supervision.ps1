# N04 post-rebuild: dual-end fill supervision smoke (--fail-on-invalid, 720h).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outDir = Join-Path $Root "results/os_state_rebuild/fill_smoke_$stamp"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[1/2] domestic --fail-on-invalid (720h) ..." -ForegroundColor Cyan
scp -o BatchMode=yes (Join-Path $Root "scripts\run_domestic_fill_audit_ack_720.ps1") "domestic-quant:C:/Users/Administrator/quant_futures/scripts/" | Out-Null
ssh -o BatchMode=yes domestic-quant "powershell -NoProfile -ExecutionPolicy Bypass -File C:/Users/Administrator/quant_futures/scripts/run_domestic_fill_audit_ack_720.ps1"
$domesticExit = $LASTEXITCODE
Write-Host "domestic_exit=$domesticExit" -ForegroundColor $(if ($domesticExit -eq 0) { "Green" } else { "Red" })

Write-Host "[2/2] overseas --fail-on-invalid (720h) ..." -ForegroundColor Cyan
ssh -o BatchMode=yes overseas-quant "cd /home/ubuntu/quant_crypto && PYTHONPATH=src:packages/fengji_core .venv/bin/python scripts/audit_paper_fills.py --profile overseas --since-hours 720 --ack-file runtime/fill_supervision_acknowledged.json --fail-on-invalid --quiet"
$overseasExit = $LASTEXITCODE
Write-Host "overseas_exit=$overseasExit" -ForegroundColor $(if ($overseasExit -eq 0) { "Green" } else { "Red" })

# Pull latest reports for record
scp -o BatchMode=yes "domestic-quant:C:/Users/Administrator/quant_futures/runtime/logs/fill_supervision/fill_supervision_domestic_latest.json" "$outDir/domestic_latest.json" 2>$null
scp -o BatchMode=yes overseas-quant:/home/ubuntu/quant_crypto/runtime/logs/fill_supervision/fill_supervision_overseas_latest.json "$outDir/overseas_latest.json" 2>$null

$summary = @{
    generated_at = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    domestic_exit = $domesticExit
    overseas_exit = $overseasExit
    out_dir = $outDir
    pass = ($domesticExit -eq 0 -and $overseasExit -eq 0)
}
$summary | ConvertTo-Json | Set-Content (Join-Path $outDir "smoke_summary.json")

if ($domesticExit -ne 0 -or $overseasExit -ne 0) {
    Write-Host "N04_FILL_SMOKE_FAIL domestic=$domesticExit overseas=$overseasExit" -ForegroundColor Red
    exit 1
}
Write-Host "N04_FILL_SMOKE_OK reports=$outDir" -ForegroundColor Green
exit 0
