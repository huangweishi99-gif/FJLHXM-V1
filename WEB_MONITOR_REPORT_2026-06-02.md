# Web Monitor Report 2026-06-02

## Scope

This report records the domestic paper-state sync work for the FengJi Web homepage monitor. It does not change strategy logic, order logic, or real trading permissions.

## Implemented

- Added `scripts/sync_domestic_paper_state.ps1`.
  - Pulls the domestic futures paper-state JSON from the configured SSH alias.
  - Validates JSON before replacing the local file.
  - Writes `runtime/domestic_paper_state.json`.
  - Writes `runtime/domestic_paper_state_meta.json`.
  - Appends sync status to `runtime/logs/domestic_paper_state_sync.log`.
  - Uses a process-level mutex to prevent overlapping scheduled/manual syncs.
- Added `scripts/install_domestic_paper_state_sync_task.ps1`.
  - Registers Windows Scheduled Task `FengJiDomesticPaperStateSync`.
  - Runs once per minute.
  - Uses PowerShell ScheduledTasks API to handle the project path with a space.
- Added `scripts/smoke_domestic_paper_state_web.ps1`.
  - Optionally syncs the domestic paper-state file.
  - Starts a temporary local API server.
  - Verifies `/api/v1/monitor/domestic/latest-opens`.
  - Stops the temporary API process.

## Verification

- Manual sync succeeded:
  - `bytes=187638`
  - `symbols=34`
  - `open_positions=18`
- Scheduled task install succeeded:
  - Task name: `FengJiDomesticPaperStateSync`
  - State: `Ready`
  - Last task result after manual trigger: `0`
- Local HTTP API smoke succeeded:
  - Endpoint: `/api/v1/monitor/domestic/latest-opens`
  - Response source: `paper_state`
  - Returned positions: `18`
- Automated smoke script succeeded:
  - Command: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\smoke_domestic_paper_state_web.ps1`
  - Output marker: `DOMESTIC_WEB_SMOKE_OK`
  - Synced at: `2026-06-02 16:37:03`
- Chinese display-name encoding check succeeded in Python:
  - Sample names decode as normal Unicode, for example `沪镍(NI)`, `甲醇(MA)`, `纯碱(SA)`, `玻璃(FG)`, `液化气(PG)`.
  - Mojibake seen in one PowerShell table output was terminal rendering, not backend data corruption.

## Current Data Flow

1. Domestic server writes the futures simulated paper-state file.
2. Local scheduled task pulls the file over SSH.
3. Local backend reads `runtime/domestic_paper_state.json`.
4. Web homepage calls `/api/v1/monitor/domestic/latest-opens`.
5. Frontend displays the latest open positions and chart detail.

## Security Notes

- No server password, API key, token, private key, or webhook URL is stored in this report.
- SSH host details should remain in local private SSH config or environment-specific configuration.
- This remains simulated trading only.

## Remaining Work

- Decide whether production should set `DOMESTIC_PAPER_STATE_PATH` explicitly or keep the default `runtime/domestic_paper_state.json`.
- Add WebSocket or polling refresh behavior for the homepage if the current polling UX is not sufficient.
