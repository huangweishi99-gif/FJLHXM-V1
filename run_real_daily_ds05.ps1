$ErrorActionPreference = "Stop"

$DataDir = "D:\BaiduNetdiskDownload\期货\实盘数据\实盘数据日K线"
$OutDir = ".\results\ds05_real_daily"

python .\src\batch_backtest_ds05.py `
    --data-dir $DataDir `
    --pattern "*日线*.csv" `
    --out-dir $OutDir `
    --initial-cash 100000 `
    --lots 1 `
    --commission-rate 0.0001 `
    --slippage-ticks 1
