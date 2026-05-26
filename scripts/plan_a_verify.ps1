# 方案 A 一键验收：依赖 + fengji_core + pytest + smoke 回测
param(
    [switch]$SkipCryptoSmoke
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "== Plan A verify: $Root ==" -ForegroundColor Cyan

Write-Host "`n[1/5] pip install requirements" -ForegroundColor Yellow
python -m pip install -r requirements.txt -r requirements-dev.txt -q
python -m pip install -e packages/fengji_core -q

Write-Host "`n[2/5] pytest" -ForegroundColor Yellow
python -m pytest tests/ -q

Write-Host "`n[3/5] DS05 sample backtest" -ForegroundColor Yellow
$ds05Out = Join-Path $Root "results\plan_a_verify\ds05"
python src\backtest_ds05.py --csv data\sample_ohlcv.csv --out-dir $ds05Out
$badDs05 = Join-Path $ds05Out "bad_trades.csv"
if (Test-Path $badDs05) {
    $lines = (Get-Content $badDs05 | Measure-Object -Line).Lines
    if ($lines -gt 1) { throw "DS05 bad_trades.csv not empty" }
}

if (-not $SkipCryptoSmoke) {
    Write-Host "`n[4/5] Unified ETH smoke (DS01-DS09)" -ForegroundColor Yellow
    $ethOut = Join-Path $Root "results\plan_a_verify\ETH"
    python src\unified_whitelist_engine.py `
        --symbol ETH `
        --daily-csv data\crypto_okx\ETH-USDT_1D_180d.csv `
        --h1-csv data\crypto_okx\ETH-USDT_1H_180d.csv `
        --m15-csv data\crypto_okx\ETH-USDT_15m_180d.csv `
        --out-dir $ethOut
    $badEth = Join-Path $ethOut "strategy_bad_trades.csv"
    if (Test-Path $badEth) {
        $lines = (Get-Content $badEth | Measure-Object -Line).Lines
        if ($lines -gt 1) { throw "ETH strategy_bad_trades.csv not empty" }
    }
} else {
    Write-Host "`n[4/5] Skipped crypto smoke (-SkipCryptoSmoke)" -ForegroundColor DarkGray
}

Write-Host "`n[5/5] fengji_core import check" -ForegroundColor Yellow
python -c "from fengji_core import FengJiOSIdentityEngine, FENGJI_TOTAL_PATTERN_STRATEGIES; assert 'DS09' in FENGJI_TOTAL_PATTERN_STRATEGIES; print('fengji_core OK', len(FENGJI_TOTAL_PATTERN_STRATEGIES), 'strategies')"

Write-Host "`nPlan A verify PASSED" -ForegroundColor Green
