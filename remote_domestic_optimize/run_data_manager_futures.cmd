@echo off
chcp 65001 >nul
cd /d "C:\Users\Administrator\quant_futures"
if not exist "runtime\logs" mkdir "runtime\logs"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1
"C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe" -u data_manager_futures.py >> "runtime\logs\data_manager_futures_run.log" 2>> "runtime\logs\data_manager_futures_err.log"
