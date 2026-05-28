# 在国内服务器跑 LC DS09：夜盘 session 校验 + 回测 + 沙盒图（结果在 runtime/sandbox/lc_ds09）
param(
    [string]$SshHost = "domestic-quant",
    [int]$MaxTrades = 3,
    [switch]$BuildFrom1h
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$buildStep = ""
if ($BuildFrom1h) {
    $buildStep = @'
$h1 = "data\1h\LC.csv"
if (-not (Test-Path $h1)) { throw "LC 1h csv missing for -BuildFrom1h" }
& $py scripts\build_lc_bars_from_1h.py --h1-csv $h1 --out-1d $d1 --out-15m $m15
if ($LASTEXITCODE -ne 0) { throw "build_lc_bars_from_1h failed" }
Write-Host "built 1d/15m from 1h ok"
'@
}
$remoteScript = @"
Set-Location C:\Users\Administrator\quant_futures
`$py = "C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"
`$env:PYTHONPATH = "src;packages/fengji_core"
`$env:FENGJI_MARKET = "futures"
`$d1 = "data\1d\LC.csv"
if (-not (Test-Path `$d1)) { `$d1 = "data\1d\LCUSDT.csv" }
`$m15 = "data\15m\LC.csv"
if (-not (Test-Path `$m15)) { `$m15 = "data\15m\LCUSDT.csv" }
$buildStep
if (-not (Test-Path `$d1) -or -not (Test-Path `$m15)) { throw "LC 1d/15m csv missing" }
`$outDir = "runtime\sandbox\lc_ds09"
New-Item -ItemType Directory -Force -Path `$outDir | Out-Null
& `$py scripts\verify_ds09_lc_session.py --d1-csv `$d1 --m15-csv `$m15 | Tee-Object "`$outDir\session_check.txt"
`$mpl = & `$py -c "import matplotlib" 2>`$null; `$LASTEXITCODE -eq 0
if (`$mpl) {
  & `$py src\plot_ds09_sandbox.py --d1-csv `$d1 --m15-csv `$m15 --trade-no 1 --out "`$outDir\LC_DS09_trade_1.png" --symbol LC --before 120 --after 80
  if (`$LASTEXITCODE -eq 0) { Write-Host "trade1_ok" }
  & `$py src\plot_ds09_sandbox.py --d1-csv `$d1 --m15-csv `$m15 --trade-no 2 --out "`$outDir\LC_DS09_trade_2.png" --symbol LC --before 120 --after 80 2>`$null
  & `$py src\plot_ds09_sandbox.py --d1-csv `$d1 --m15-csv `$m15 --trade-no 3 --out "`$outDir\LC_DS09_trade_3.png" --symbol LC --before 120 --after 80 2>`$null
} else {
  "matplotlib_missing=skip_sandbox_plots" | Out-File "`$outDir\summary.txt" -Encoding utf8 -Append
}
& `$py -u src\fengji_radar_order_loop.py --once --data-dir data --symbols LC --radar-dir runtime\fengji_radar --pending-dir runtime\fengji_pending_orders --monitor-state runtime\fengji_pending_orders\futures_pending_state.json --daily-tail 400 --h1-tail 2400 --top-n 10 2>&1 | Select-Object -Last 4
`$radar = Get-Content runtime\fengji_radar\radar.json -Raw | ConvertFrom-Json
`$ds09 = @(`$radar | Where-Object { `$_.strategy_id -eq 'DS09' })
"DS09_radar_rows=`$(`$ds09.Count)" | Out-File "`$outDir\summary.txt" -Encoding utf8
Get-ChildItem `$outDir | Select-Object Name, Length, LastWriteTime
"@

Write-Host "Sync scripts to domestic ..." -ForegroundColor Cyan
$files = @(
    "scripts\verify_ds09_lc_session.py",
    "src\plot_ds09_sandbox.py",
    "src\fengji_total_radar.py",
    "src\fengji_radar_order_loop.py",
    "packages\fengji_core\fengji_core\ds09.py",
    "packages\fengji_core\fengji_core\data.py",
    "src\backtest_ds09.py",
    "scripts\build_lc_bars_from_1h.py",
    "scripts\verify_ds09_lc_session.py"
)
foreach ($rel in $files) {
    $local = Join-Path $Root $rel
    $remotePath = "C:/Users/Administrator/quant_futures/" + ($rel -replace '\\', '/')
    $remoteDir = Split-Path $remotePath -Parent
    $enc = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes("New-Item -ItemType Directory -Force -Path '$remoteDir' | Out-Null"))
    ssh -o BatchMode=yes $SshHost "powershell -NoProfile -EncodedCommand $enc" | Out-Null
    scp -o BatchMode=yes $local "${SshHost}:$remotePath"
}

$encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($remoteScript))
Write-Host "Run LC DS09 on domestic ..." -ForegroundColor Cyan
ssh -o BatchMode=yes $SshHost "powershell -NoProfile -EncodedCommand $encoded"

$localOut = Join-Path $Root "results\sandbox\lc_ds09_domestic"
New-Item -ItemType Directory -Force -Path $localOut | Out-Null
scp -o BatchMode=yes -r "${SshHost}:/Users/Administrator/quant_futures/runtime/sandbox/lc_ds09/*" $localOut
Write-Host "Saved sandbox to $localOut" -ForegroundColor Green
