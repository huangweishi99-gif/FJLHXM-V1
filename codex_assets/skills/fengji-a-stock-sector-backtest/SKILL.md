---
name: fengji-a-stock-sector-backtest
description: Reusable domestic A-share FengJi sector backtest workflow. Use when continuing sector backtests, rerunning failed stocks, switching free data sources, summarizing sector performance, archiving results, or reporting A-share progress separately from crypto and futures.
---

# FengJi A-Stock Sector Backtest

## Core rule

Report A-share progress as its own workstream. Do not merge it into crypto or futures status. Strategy evaluation must remain under FengJi OS highest constitution.

## Standard workflow

1. Confirm board name/code and resume point.
2. Generate or inspect the stock pool before running a full backtest.
3. Run the batch backtest with explicit output directory.
4. Retry failed symbols using available data sources before marking them failed.
5. Inspect `a_stock_sector_batch_summary.csv` and per-stock `stock_summary.csv`.
6. Archive or update the sector summary.
7. Report top results, failures, data limits, and next board.

## PowerShell command pattern

Use PowerShell syntax, not CMD syntax:

```powershell
Set-Location "C:\Users\guangwan\Documents\New project"

& "C:\Users\guangwan\AppData\Local\Programs\Python\Python312\python.exe" ".\src\batch_backtest_a_stock_sector.py" `
  --boards "CPO概念" `
  --top-n 28 `
  --sort-by amount `
  --data-source auto `
  --db ".\data\market_data.sqlite" `
  --out-dir ".\results\fengji_total_a_stock_sectors_cpo_ds07_fixed"
```

Do not use `cd /d` in PowerShell. Do not omit the leading `&` before a quoted Python path.

## Known evidence locations

- Review doc: `docs\FENGJI_TOTAL_A_STOCK_HOT20_REVIEW.md`.
- Entry scripts:
  - `src\backtest_a_stock_fengji.py`
  - `src\batch_backtest_a_stock_fengji.py`
  - `src\batch_backtest_a_stock_sector.py`
- Hot-20 fixed summary: `results\fengji_total_a_stock_hot20_ds07_fixed\a_stock_hot20_summary.csv`.
- Sector fixed summaries are usually under `results\fengji_total_a_stock_sectors_*_ds07_fixed`.

Known completed/seen board families include CPO, 算力, 半导体, 虚拟机器人, 航空装备, and related archived sector summaries. Verify the current file state before claiming completion.

## Data-source retry policy

If a stock fails:

1. Retry the symbol once with the normal `auto` path.
2. Try the configured fallback source if the script supports it.
3. If Eastmoney intraday history is too short, state that DS07/DS08 intraday claims are limited.
4. Do not claim DS01-DS08 full historical completeness when 60-minute coverage is insufficient.

## Result report format

Include:

- Board name and output directory.
- Number of symbols requested, succeeded, failed.
- Top 5 by total return and their max drawdown.
- `bad_audits` status.
- Data limitations, especially 60-minute coverage.
- Exact next board or failed-symbol retry list.

