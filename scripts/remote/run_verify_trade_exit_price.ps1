# Server-side: verify PG exit_price coverage after context refresh.
param(
    [string]$Root = "C:\Users\Administrator\quant_futures"
)

$ErrorActionPreference = "Stop"
Set-Location $Root
$env:PYTHONPATH = "services;packages/fengji_core"
python (Join-Path $Root "scripts\verify_trade_exit_price_coverage.py") --pg
