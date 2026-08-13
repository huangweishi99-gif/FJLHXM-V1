Set-Location "C:\Users\Administrator\quant_futures"
$env:PYTHONPATH = "src;packages\fengji_core"
py -3 scripts\audit_paper_fills.py --profile domestic --since-hours 720 --fail-on-invalid
exit $LASTEXITCODE
