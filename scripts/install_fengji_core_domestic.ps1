$ErrorActionPreference = "Stop"
Set-Location "C:\Users\Administrator\quant_futures"
$env:PYTHONPATH = "src"
$py = "C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"
& $py -m pip install -e packages\fengji_core -q
& $py -c "from quant.os_engine import FengJiOSIdentityEngine; print('fengji_core_domestic_ok')"
