# Domestic fill_supervision 72h smoke
Set-Location "C:\Users\Administrator\quant_futures"
$env:FENGJI_MARKET = "futures"
$env:PYTHONPATH = "src;packages\fengji_core"
python scripts/audit_paper_fills.py --root . --profile domestic --since-hours 72 --quiet
Write-Output "exit=$LASTEXITCODE"
