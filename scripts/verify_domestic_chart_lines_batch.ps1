# Post-deploy: 国内期货峰极连线批量审计（chart_line + OS state）。
param(
    [string]$Symbols = "AG,SC,NI,RB,LC",
    [string]$Root = "C:\Users\Administrator\quant_futures"
)

$ErrorActionPreference = "Stop"
Set-Location $Root
$env:PYTHONPATH = "src;packages/fengji_core;services"

& python scripts/audit_fengji_chart_lines.py --symbols $Symbols
exit $LASTEXITCODE
