# FengJi OS DS01-DS08 Quant Backtest

This project implements a codable subset extracted from the two provided Word documents:

- FengJi OS constitution V5 runtime / patch version
- FengJi OS DS05 finger-pattern final whitepaper

The implemented strategy is DS05 "Finger Pattern": an extreme-zone counterattack pattern authorized by FengJi OS.

## Source Of Truth

The Word documents are historical references. If they conflict with the current project code, sandbox chart behavior, or [docs/CANONICAL_RULES.md](docs/CANONICAL_RULES.md), this project wins.

Current physical sandbox charts use `hardened_fengji_line` as the main FengJi line: hardened 3-3/T+3 HIGH/LOW nodes connected by straight line segments in peak-extreme-peak-extreme order.

All DS01-DS09 strategies in the current FengJi Total Pattern must inherit this project's current FengJi OS and red/blue camp transition rules. Uploaded documents are only references for each strategy's buy/sell trigger logic, not for OS constitution, line rules, or camp rules. DS09 (D1 + M15) is included when M15 data is available.

DS01-DS09 are the current FengJi Total Pattern. See the calibration documents in `docs/` and `docs/DS09_IN_TOTAL_PATTERN.md`.

The same red/blue camp state machine applies to every strategy and timeframe: daily, hourly, and 5-minute bars.

## Extracted Trading Rules

FengJi OS base:

- Raw nodes use 3-3 / T+3 confirmation. A node at bar T is only released after T+3 closes.
- If one bar is both HIGH and LOW, keep HIGH for bullish candle, keep LOW for bearish candle, discard doji.
- Hardened nodes must alternate HIGH and LOW.
- Consecutive HIGH keeps the higher one; consecutive LOW keeps the lower one.
- Adjacent opposite node `point_idx` distance must be at least `gap`, default 3. This means there must be at least two full K bars between a peak and an extreme.
- If multiple bars share the same highest high or lowest low inside the 3-3 window, the latest bar is the valid peak/extreme candidate.
- Camp is a state machine: red = long camp, blue = short camp, neutral = no authorization.
- Defense extreme break causes camp transition.
- Failed points enter `identity_nodes` as logs, but only legal PEAK/EXT nodes enter `identity_line`.

DS05 signal:

- Long only in red camp. Short only in blue camp.
- K2 and K3 must be in the same camp.
- Long: K2 makes a lower low near active red extreme, K3 does not break K2 low, and K3 breaks K2 high.
- Short: K2 makes a higher high near active blue extreme, K3 does not break K2 high, and K3 breaks K2 low.
- K2 must not gap away from K1.
- Extreme proximity uses ATR tolerance, default `0.80 * ATR`.
- Entry is same-bar trigger:
  - Long entry = `max(K3.open, K2.high)`
  - Short entry = `min(K3.open, K2.low)`
- Initial stop is K2 low for long, K2 high for short.
- Dynamic stop follows DS02-style rule:
  - Long stop only moves up on bullish candles, using that candle's low.
  - Short stop only moves down on bearish candles, using that candle's high.
- Trade audit must prove there is no short in red camp and no long in blue camp.

## Run

Install dependencies:

```powershell
pip install -r requirements.txt
```

Generate sample OHLCV data:

```powershell
python scripts/generate_sample_data.py --out data/sample_ohlcv.csv
```

Run DS05 backtest:

```powershell
python src/backtest_ds05.py --csv data/sample_ohlcv.csv --out-dir results/ds05_sample
```

If Python was installed through IDLE but `python` is not in PATH, use the helper script:

```powershell
.\run_ds05.ps1
```

Or call Python with its full path:

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" src\backtest_ds05.py --csv data\sample_ohlcv.csv --out-dir results\ds05_sample
```

Batch run local futures daily data:

```powershell
python src\batch_backtest_ds05.py --data-dir "D:\BaiduNetdiskDownload\期货\实盘数据\实盘数据日K线" --pattern "*日线*.csv" --out-dir results\ds05_real_daily
```

Realistic futures capital model:

```powershell
python src\batch_backtest_ds05.py `
  --data-dir "D:\BaiduNetdiskDownload\期货\实盘数据\实盘数据日K线" `
  --pattern "*日线*.csv" `
  --out-dir results\ds05_real_daily_futures `
  --initial-cash 100000 `
  --lots 1 `
  --commission-rate 0.0001 `
  --slippage-ticks 1
```

The futures model uses:

- Initial cash: 100,000
- Position size: fixed 1 lot
- PnL: price difference x contract multiplier x lots
- Fee: notional x 0.0001 per entry/exit
- Slippage: 1 adverse tick per fill
- Margin: notional x configured product margin rate
- Margin is a capital constraint, not a cash cost

Or:

```powershell
.\run_real_daily_ds05.ps1
```

Generate sandbox charts for the last N DS05 trades:

```powershell
python src\batch_plot_ds05_sandbox.py `
  --csv "D:\BaiduNetdiskDownload\期货\实盘数据\实盘数据日K线\棉花_日线_5年.csv" `
  --last 7 `
  --out-dir results\sandbox\cotton_last7 `
  --futures-mode
```

Run the FengJi Total Pattern whitelist ledger for one symbol:

```powershell
python src\unified_whitelist_engine.py `
  --symbol 生猪 `
  --daily-csv "D:\BaiduNetdiskDownload\期货\实盘数据\实盘数据日K线\生猪_日线_5年.csv" `
  --h1-csv "D:\BaiduNetdiskDownload\期货\实盘数据\5-60分钟csv\生猪_60m.csv" `
  --m15-csv "D:\BaiduNetdiskDownload\期货\实盘数据\5-60分钟csv\生猪_15m.csv" `
  --out-dir results\unified_smoke\生猪
```

Run the FengJi Total Pattern whitelist ledger in batch:

```powershell
python src\batch_unified_whitelist_engine.py `
  --whitelist 生猪,碳酸锂,乙二醇 `
  --daily-dir "D:\BaiduNetdiskDownload\期货\实盘数据\实盘数据日K线" `
  --minute-dir "D:\BaiduNetdiskDownload\期货\实盘数据\5-60分钟csv" `
  --out-dir results\unified_whitelist
```

Unified outputs:

- `candidate_trades.csv`
- `accepted_trades.csv`
- `rejected_orders.csv`
- `ledger_events.csv`
- `strategy_bad_trades.csv`
- `whitelist_summary.csv` for batch runs

Run the FengJi Total Pattern crypto whitelist review on OKX historical bars:

```powershell
python src\batch_unified_crypto_whitelist.py `
  --symbols BTC-USDT,ETH-USDT,SOL-USDT `
  --days 180 `
  --leverage 2 `
  --margin-per-trade 200 `
  --out-dir results\unified_crypto_whitelist_core_180d
```

Crypto whitelist admission is gated by historical live-data review first. DS09 is part of the FengJi Total Pattern; fetch M15 bars with `scripts/fetch_crypto_m15_for_ds09.py` before backtests. The current DS01-DS08 5-year review is documented in [docs/FENGJI_TOTAL_DS01_DS08_CRYPTO_5Y_REVIEW.md](docs/FENGJI_TOTAL_DS01_DS08_CRYPTO_5Y_REVIEW.md) (DS09+M15 full reruns use `batch_unified_crypto_whitelist.py` defaults).

The latest 30-day forward review is documented in [docs/CRYPTO_FORWARD30_M15_REVIEW.md](docs/CRYPTO_FORWARD30_M15_REVIEW.md). No crypto symbol is approved for live auto-trading yet; ETH and XRP only have restricted observation rules.

Run the all-in-one observation-only realtime monitor:

```powershell
python src\crypto_combined_monitor.py `
  --symbols ETH-USDT `
  --lookback-hours 24 `
  --out-dir results\crypto_combined_monitor
```

The canonical FengJi Total Pattern crypto system is documented in [docs/CRYPTO_COMBINED_SYSTEM.md](docs/CRYPTO_COMBINED_SYSTEM.md). It checks DS01-DS09 together and never places live orders.

The full FengJi Total Pattern specification is documented in [docs/FENGJI_TOTAL_PATTERN_SPEC.md](docs/FENGJI_TOTAL_PATTERN_SPEC.md).

The latest FengJi Total Pattern crypto 180-day review is documented in [docs/FENGJI_TOTAL_PATTERN_CRYPTO_180D_REVIEW.md](docs/FENGJI_TOTAL_PATTERN_CRYPTO_180D_REVIEW.md).

DS01 has been calibrated on the current OS. See [docs/DS01_DRAFT.md](docs/DS01_DRAFT.md) and [docs/DS01_CALIBRATION.md](docs/DS01_CALIBRATION.md).

DS02 has been calibrated on the current OS. See [docs/DS02_DRAFT.md](docs/DS02_DRAFT.md) and [docs/DS02_CALIBRATION.md](docs/DS02_CALIBRATION.md).

DS03 has been calibrated on the current OS. See [docs/DS03_DRAFT.md](docs/DS03_DRAFT.md) and [docs/DS03_CALIBRATION.md](docs/DS03_CALIBRATION.md).

DS04 has been calibrated on the current OS. See [docs/DS04_DRAFT.md](docs/DS04_DRAFT.md) and [docs/DS04_CALIBRATION.md](docs/DS04_CALIBRATION.md).

DS05 has been calibrated on the current OS. See [docs/DS05_CALIBRATION.md](docs/DS05_CALIBRATION.md).

DS06 has been calibrated on the current OS. See [docs/DS06_DRAFT.md](docs/DS06_DRAFT.md) and [docs/DS06_CALIBRATION.md](docs/DS06_CALIBRATION.md).

DS07 has been calibrated on the current OS. See [docs/DS07_DRAFT.md](docs/DS07_DRAFT.md) and [docs/DS07_CALIBRATION.md](docs/DS07_CALIBRATION.md).

DS08 has been calibrated on the current OS. See [docs/DS08_DRAFT.md](docs/DS08_DRAFT.md) and [docs/DS08_CALIBRATION.md](docs/DS08_CALIBRATION.md).

DS09 has been calibrated on the current OS. See [docs/DS09_DRAFT.md](docs/DS09_DRAFT.md) and [docs/DS09_CALIBRATION.md](docs/DS09_CALIBRATION.md).

Expected CSV columns:

```text
date,open,high,low,close,volume
```

## Outputs

When `--out-dir` is provided, the runner writes:

- `trades.csv`
- `bad_trades.csv`
- `equity.csv`
- `raw_nodes.csv`
- `identity_nodes.csv`
- `turns.csv`
- `os_log.csv`

`bad_trades.csv` should be empty for a valid DS05 run.

## Key Files

```text
packages/fengji_core/      FengJi OS + DS01-DS09 core (pip install -e)
docs/PLAN_A_ROADMAP.md     Plan A engine stabilization roadmap
scripts/plan_a_verify.ps1  One-click install verification
src/backtest_ds05.py       DS05 backtest CLI
src/quant/os_engine.py     FengJi OS identity engine
src/quant/ds05.py          DS05 signal, stop, camp audit
src/quant/data.py          CSV loading and ATR
src/unified_whitelist_engine.py  Single-symbol DS01-DS09 ledger
src/batch_unified_whitelist_engine.py  Batch whitelist ledger
src/batch_unified_crypto_whitelist.py  OKX crypto DS01-DS09 whitelist review
scripts/fetch_crypto_m15_for_ds09.py  Download OKX 15m bars for DS09
src/crypto_combined_monitor.py  All-in-one observation-only OKX crypto monitor
src/crypto_realtime_monitor.py  Research-only restricted observation monitor
src/backtest.py            Original moving-average demo
```

## Notes

The current implementation is offline and CSV-driven. The documents also mention crypto/futures data adapters, leverage, liquidation, contract multipliers, and market DNA whitelists. Those are intentionally kept outside the core DS05 logic so the OS and signal rules remain auditable.
