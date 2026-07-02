# Remote backtest trade PnL smoke via SSH tunnel to domestic API.
param(
    [string]$SshHost = "domestic-quant",
    [int]$LocalPort = 8045,
    [int]$RemotePort = 8000
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "=== backtest trade PnL smoke (SSH tunnel) ===" -ForegroundColor Cyan
python (Join-Path $PSScriptRoot "smoke_w14_backtest_trade_pnl.py") `
    --ssh-tunnel $SshHost `
    --local-port $LocalPort `
    --remote-port $RemotePort
