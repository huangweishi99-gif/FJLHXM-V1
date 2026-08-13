# 海外 + 国内挂单监控全品种验收（每品种 N 轮，默认 10）
param(
    [int]$Rounds = 10,
    [string]$OverseasHost = "overseas-quant",
    [string]$DomesticHost = "domestic-quant",
    [string]$OverseasDir = "/home/ubuntu/quant_crypto",
    [string]$DomesticDir = "/Users/Administrator/quant_futures"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$ScriptRel = "scripts/verify_pending_monitor_all_symbols.py"
$LocalScript = Join-Path $Root $ScriptRel
$Ts = Get-Date -Format "yyyyMMdd_HHmmss"
$OutDir = Join-Path $Root "results\pending_monitor_verify_$Ts"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

function Sync-Script([string]$HostAlias, [string]$RemoteDir) {
    $remoteParent = ($RemoteDir -replace '\\', '/').TrimEnd('/')
    ssh -o BatchMode=yes -o ConnectTimeout=20 $HostAlias "mkdir -p ${remoteParent}/scripts"
    scp -o BatchMode=yes -o ConnectTimeout=20 $LocalScript "${HostAlias}:${remoteParent}/scripts/verify_pending_monitor_all_symbols.py"
}

function Run-RemoteVerify([string]$HostAlias, [string]$RemoteDir, [string]$Market, [string]$OutName) {
    $remoteParent = ($RemoteDir -replace '\\', '/').TrimEnd('/')
    $jsonRemote = "${remoteParent}/runtime/logs/${OutName}.json"
    if ($Market -eq "futures") {
        $cmd = "cmd.exe /d /c C:\Users\Administrator\quant_futures\scripts\run_verify_domestic_pending.bat"
        $jsonRemote = "${remoteParent}/runtime/logs/verify_futures.json"
    } else {
        $cmd = "cd ${remoteParent} && FENGJI_MARKET=crypto PYTHONPATH=src:packages/fengji_core .venv/bin/python scripts/verify_pending_monitor_all_symbols.py --market crypto --rounds $Rounds --root ${remoteParent} --json-out ${jsonRemote}"
    }
    Write-Host "[$HostAlias][$Market] running $Rounds rounds/symbol ..." -ForegroundColor Cyan
    ssh -o BatchMode=yes -o ConnectTimeout=20 $HostAlias $cmd
    $localJson = Join-Path $OutDir "${OutName}.json"
    scp -o BatchMode=yes -o ConnectTimeout=20 "${HostAlias}:${jsonRemote}" $localJson
    return $localJson
}

Write-Host "=== Sync verify script ===" -ForegroundColor Yellow
Sync-Script $OverseasHost $OverseasDir
Sync-Script $DomesticHost $DomesticDir
$batLocal = Join-Path $Root "scripts\run_verify_domestic_pending.bat"
scp -o BatchMode=yes -o ConnectTimeout=20 $batLocal "${DomesticHost}:/Users/Administrator/quant_futures/scripts/run_verify_domestic_pending.bat"

$overseasJson = Run-RemoteVerify $OverseasHost $OverseasDir "crypto" "verify_crypto_${Ts}"
$domesticJson = Run-RemoteVerify $DomesticHost $DomesticDir "futures" "verify_futures_${Ts}"

$summaryPath = Join-Path $OutDir "SUMMARY.md"
$lines = @(
    "# 挂单监控全品种验收 · $Ts",
    "",
    "每品种 **$Rounds** 轮 · 海外 crypto + 国内期货",
    "",
    "## 结果文件",
    "- overseas: ``$overseasJson``",
    "- domestic: ``$domesticJson``",
    ""
)

foreach ($pair in @(@("海外 crypto", $overseasJson), @("国内期货", $domesticJson))) {
    $label = $pair[0]
    $path = $pair[1]
    if (-not (Test-Path $path)) {
        $lines += "## $label", "- **FAIL** 无结果文件", ""
        continue
    }
    $r = Get-Content $path -Raw -Encoding UTF8 | ConvertFrom-Json
    $status = if ($r.all_symbols_pass) { "PASS" } else { "FAIL" }
    $lines += @(
        "## $label",
        "- 状态: **$status**",
        "- 品种数: $($r.symbol_count) · 总轮次: $($r.total_checks) · 通过: $($r.passed_rounds) · 失败: $($r.failed_rounds)",
        "- process_once 烟测: $(if ($r.process_once_smoke.ok) { 'OK' } else { 'FAIL ' + $r.process_once_smoke.error })"
    )
    if ($r.failed_symbols -and $r.failed_symbols.Count -gt 0) {
        $lines += "- 失败品种: $($r.failed_symbols -join ', ')"
    }
    $lines += ""
}

$lines | Set-Content -LiteralPath $summaryPath -Encoding UTF8
Write-Host "`nSummary: $summaryPath" -ForegroundColor Green
Get-Content $summaryPath -Encoding UTF8

$fail = 0
foreach ($p in @($overseasJson, $domesticJson)) {
    if (-not (Test-Path $p)) { $fail++; continue }
    $r = Get-Content $p -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $r.all_symbols_pass) { $fail++ }
}
if ($fail -gt 0) { exit 1 }
exit 0
