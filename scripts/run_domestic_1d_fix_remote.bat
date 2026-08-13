@echo off
cd /d C:\Users\Administrator\quant_futures
echo === force 1d refresh ===
python scripts\force_domestic_1d_refresh.py
echo exit=%ERRORLEVEL%
echo === audit 1d ===
python runtime\_tmp_audit_remote_1d.py --d1-dir data/1d --min-date 2026-06-19
echo === restart dm ===
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\ensure_single_data_manager.ps1
