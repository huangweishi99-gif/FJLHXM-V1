# 方案 A：拉取 15m + 十币九定式 180 天回测
param(
    [int]$Days = 180,
    [string]$Symbols = "DEFAULT",
    [string]$OutDir = "results/plan_a_crypto_180d"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "== Plan A crypto batch: days=$Days symbols=$Symbols ==" -ForegroundColor Cyan

Write-Host "`n[1/2] Fetch M15 for DS09" -ForegroundColor Yellow
python scripts\fetch_crypto_m15_for_ds09.py --symbols $Symbols --days $Days --refresh

Write-Host "`n[2/2] Unified whitelist backtest" -ForegroundColor Yellow
python src\batch_unified_crypto_whitelist.py `
    --symbols $Symbols `
    --days $Days `
    --out-dir $OutDir

Write-Host "`nSummary: $OutDir\crypto_whitelist_summary.csv" -ForegroundColor Green
