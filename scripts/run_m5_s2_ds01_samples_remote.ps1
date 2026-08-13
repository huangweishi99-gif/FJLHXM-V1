Set-Location "C:\Users\Administrator\quant_futures"
$env:PYTHONPATH = "src;packages/fengji_core"
& py -3 scripts/plot_m5_s2_ds01_samples.py
