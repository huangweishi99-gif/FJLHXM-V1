Set-Location "C:\Users\Administrator\quant_futures"
$env:PYTHONPATH = "src;packages/fengji_core"
& py -3 scripts/plot_m5_b_zone_ds01_batch.py --profile domestic --skip-existing
