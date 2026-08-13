Set-Location "C:/Users/Administrator/quant_futures"
$env:PYTHONPATH = "src;packages/fengji_core"
python scripts/audit_paper_fills.py --profile domestic --since-hours 720 --ack-file runtime/fill_supervision_acknowledged.json --fail-on-invalid --quiet
exit $LASTEXITCODE
