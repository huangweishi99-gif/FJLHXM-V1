$ErrorActionPreference = "Stop"
Set-Location "C:\Users\Administrator\quant_futures"
$env:PYTHONPATH = "src"
$py = "C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"
& $py -m py_compile src\quant\ds05.py src\fengji_total_radar.py src\backtest_ds05.py src\batch_backtest_ds05_crypto.py src\plot_ds05_sandbox.py scripts\check_ds05_k2_possible_extreme.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $py scripts\check_ds05_k2_possible_extreme.py
