@echo off
cd /d "C:\Users\Administrator\quant_futures"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_futures_pending_monitor.ps1"
