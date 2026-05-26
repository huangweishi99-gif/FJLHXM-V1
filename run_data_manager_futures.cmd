@echo off
chcp 65001 >nul
cd /d "C:\Users\Administrator\quant_futures"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Users\Administrator\quant_futures\run_data_manager_futures.ps1"
