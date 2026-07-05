# 夜盘 PG/SC 15m 验收：轮询直到 ACCEPTANCE_OK，通过后跑 domestic health。
param(
    [int]$IntervalSec = 300,
    [int]$MaxWaitMin = 180
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

Write-Host "=== Night session PG/SC acceptance ===" -ForegroundColor Cyan
powershell -NoProfile -File (Join-Path $root "scripts\wait_pg_sc_15m_acceptance.ps1") `
    -IntervalSec $IntervalSec -MaxWaitMin $MaxWaitMin
$code = $LASTEXITCODE
if ($code -ne 0) { exit $code }

Write-Host "`n=== Post-acceptance domestic health ===" -ForegroundColor Cyan
powershell -NoProfile -File (Join-Path $root "scripts\verify_domestic_health.ps1")
exit $LASTEXITCODE
