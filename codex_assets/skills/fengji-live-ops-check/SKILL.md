---
name: fengji-live-ops-check
description: Reusable FengJi live/paper runtime health-check workflow for this project. Use when checking domestic or overseas servers, data pumps, paper-trading monitors, Dash terminals, pending-order loops, log freshness, SSH/scp deployment status, or whether crypto/futures/A-share simulation processes are running correctly.
---

# FengJi Live Ops Check

## Core rule

Treat every runtime check as evidence collection first. Do not change strategy logic while checking service health. All strategy conclusions must remain under FengJi OS highest constitution.

## Evidence order

1. Identify target: overseas crypto server, domestic Windows futures/A-share server, or local workspace.
2. Check processes before reading logs.
3. Check log freshness and latest error lines.
4. Check data freshness by timeframe and symbol.
5. If pending orders are involved, check radar output, pending order CSV/JSON, and monitor fill log.
6. Report current status, last known data time, failures, and exact next action.

## Known environments

- Overseas crypto server: `ubuntu@43.167.10.79`, project `~/quant_crypto`.
- Domestic Windows server: `Administrator@106.53.107.248`, project `C:\Users\Administrator\quant_futures`.
- Local workspace: `C:\Users\guangwan\Documents\New project`.

Do not expose webhook URLs, passwords, private keys, or full secret values in responses.

## Overseas crypto check

Use SSH to gather:

```bash
cd ~/quant_crypto
pgrep -af "data_manager.py|overseas_paper_monitor.py|fengji_pending_order_monitor|fengji_radar_order_loop" || true
tail -n 120 paper_run.log
tail -n 120 data_sync.log
tail -n 80 pending_order_monitor.log 2>/dev/null || true
find data -type f -name "*.csv" -printf "%TY-%Tm-%Td %TH:%TM:%TS %p\n" | sort | tail -60
date
date -u
```

Healthy evidence usually includes:

- `data_manager.py` process is present.
- `overseas_paper_monitor.py` process is present, unless pending-order monitor has intentionally taken over entry handling.
- Data files update near expected timeframe cadence.
- Logs show repeated no-signal/check/fill lines without tracebacks.

## Domestic Windows check

Use SSH to gather:

```powershell
Set-Location "C:\Users\Administrator\quant_futures"
Get-Date
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -match 'data_manager_futures.py|峰极总定式01-08国内期货A股模拟实盘|商业终端_Dash.py|fengji_futures_pending_order_monitor|fengji_radar_order_loop' } |
  Select-Object ProcessId,CommandLine
Get-ChildItem -File *.log,logs\*.log -ErrorAction SilentlyContinue |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 12 FullName,Length,LastWriteTime
```

For futures data issues, verify whether `data_manager_futures.py` is using long-lived TqApi connection reuse. Do not change futures/A-share buy/sell rules during data-pump repairs.

## Deployment check

Before copying files to a server:

1. Identify exact changed files.
2. Prefer `scp` only for those files.
3. Run syntax/tests locally or on the server when possible.
4. Restart only the affected service/process.
5. Re-check processes and tail logs.

Never use broad deletes, broad overwrites, or unverified recursive syncs for this project.

## Response format

Keep the answer short:

- `运行状态`: normal/degraded/stopped.
- `数据状态`: latest data times and any stale timeframe.
- `日志状态`: last errors or no errors.
- `需要处理`: one concrete next action.

