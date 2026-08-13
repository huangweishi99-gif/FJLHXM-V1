@echo off
cd /d C:\Users\Administrator\quant_futures
set FENGJI_MARKET=futures
set PYTHONPATH=src;packages/fengji_core
python scripts\verify_pending_monitor_all_symbols.py --market futures --rounds 10 --quiet --json-out runtime\logs\verify_futures.json > runtime\logs\verify_futures_run.log 2>&1
exit /b %ERRORLEVEL%
