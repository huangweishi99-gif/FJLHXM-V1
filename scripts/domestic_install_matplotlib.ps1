# 在国内服务器安装 matplotlib（LC DS09 沙盒图；Python 3.10）
$ErrorActionPreference = "Stop"
$py = "C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"
& $py -m pip install matplotlib -q
& $py -c "import matplotlib; print('matplotlib', matplotlib.__version__)"
