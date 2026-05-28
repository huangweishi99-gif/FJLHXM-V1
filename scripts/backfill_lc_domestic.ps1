# 国内服务器：加长抓取 LC 的 1d/1h/15m（供 DS09 回测/沙盒）
param(
    [string]$SshHost = "domestic-quant",
    [int]$M15Length = 12000,
    [int]$D1Length = 800
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$RemoteRoot = "C:/Users/Administrator/quant_futures"

Write-Host "Sync files ..." -ForegroundColor Cyan
@(
    "data_manager_futures.py",
    "scripts/backfill_lc_on_server.py",
    "scripts/repair_lc_15m_only.py",
    "packages/fengji_core/fengji_core/data.py",
    "src/backtest_ds09.py",
    "scripts/verify_ds09_lc_session.py",
    "src/plot_ds09_sandbox.py",
    "scripts/plot_lc_ds09_session_overview.py"
) | ForEach-Object {
    $local = Join-Path $Root $_
    $remote = "$RemoteRoot/" + ($_ -replace '\\', '/')
    scp -o BatchMode=yes $local "${SshHost}:${remote}"
}

$remoteRun = @"
Set-Location '$RemoteRoot'
`$env:FUTURES_15M_LENGTH = '$M15Length'
`$env:FUTURES_1D_LENGTH = '$D1Length'
`$py = 'C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe'
& `$py scripts/backfill_lc_on_server.py
"@
$encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($remoteRun))
Write-Host "Backfill LC (15m=$M15Length) ..." -ForegroundColor Cyan
ssh -o BatchMode=yes $SshHost "powershell -NoProfile -EncodedCommand $encoded"
