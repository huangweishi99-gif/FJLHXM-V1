@echo off
cd /d C:\Users\Administrator\quant_futures
set FENGJI_MARKET=futures
set PYTHONPATH=src;packages/fengji_core
python scripts\audit_os_state_freshness_all.py --market futures --fix --quiet > runtime\logs\os_freshness_run.log 2>&1
exit /b %ERRORLEVEL%
