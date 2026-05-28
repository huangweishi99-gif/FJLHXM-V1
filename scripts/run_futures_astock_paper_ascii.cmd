@echo off
cd /d C:\Users\Administrator\quant_futures
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\Administrator\quant_futures\run_futures_astock_paper.ps1"
