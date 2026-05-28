$ErrorActionPreference = "Stop"
Set-Location "C:\Users\Administrator\quant_futures"
$env:PYTHONPATH = "src"
$py = "C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"
& $py scripts\check_ds04_fg_sa_20260526.py data
