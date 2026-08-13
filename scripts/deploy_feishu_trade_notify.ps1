# 飞书四类挂单通知 + 发送前自检：同步双端并重启挂单监控
param(
    [switch]$OverseasOnly,
    [switch]$DomesticOnly
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

$shared = @(
    "packages/fengji_core/fengji_core/feishu_trade_notify.py",
    "packages/fengji_core/fengji_core/fill_supervision.py",
    "src/fengji_feishu_notify.py"
)
$overseasExtra = @(
    "src/fengji_pending_order_monitor.py",
    "src/fengji_feishu_paper_notify.py",
    "src/overseas_paper_monitor.py",
    "scripts/watchdog_overseas.sh"
)
$domesticExtra = @(
    "src/fengji_pending_order_monitor.py",
    "src/fengji_futures_pending_order_monitor.py",
    "src/fengji_feishu_paper_notify.py"
)
$domesticPaperRemote = "C:/Users/Administrator/quant_futures/runtime/_deploy_domestic_paper_tmp.py"

function Deploy-DomesticPaper([string]$ProjectRoot) {
    $paperLocal = Resolve-DomesticPaperLocal $ProjectRoot
    scp -o BatchMode=yes -o ConnectTimeout=30 $paperLocal "domestic-quant:$domesticPaperRemote"
    if ($LASTEXITCODE -ne 0) { throw "scp domestic paper failed" }
    $manifestLocal = Join-Path $ProjectRoot "scripts\domestic_paper_manifest.txt"
    scp -o BatchMode=yes $manifestLocal "domestic-quant:C:/Users/Administrator/quant_futures/scripts/domestic_paper_manifest.txt"
    $remotePs = @'
$r = 'C:/Users/Administrator/quant_futures'
$n = (Get-Content "$r/scripts/domestic_paper_manifest.txt" -Encoding UTF8 | Select-Object -First 1).Trim()
Copy-Item "$r/runtime/_deploy_domestic_paper_tmp.py" (Join-Path $r $n) -Force
Remove-Item "$r/runtime/_deploy_domestic_paper_tmp.py" -Force
Write-Output "deployed $n"
'@
    $remotePs | ssh -o BatchMode=yes domestic-quant "powershell -NoProfile -Command -"
    Write-Host "synced domestic-quant: domestic paper (via temp path)"
}

function Sync-List([string]$HostAlias, [string]$RemoteRoot, [string[]]$Files) {
    foreach ($rel in $Files) {
        $local = Join-Path $root ($rel -replace "/", "\")
        if (-not (Test-Path -LiteralPath $local)) { throw "missing: $local" }
        $remote = "$RemoteRoot/$($rel -replace '\\','/')"
        $remoteDir = ($remote -replace '/[^/]+$', '')
        if ($HostAlias -eq "domestic-quant") {
            ssh -o BatchMode=yes $HostAlias "if (-not (Test-Path '$remoteDir')) { New-Item -ItemType Directory -Force -Path '$remoteDir' | Out-Null }"
        } else {
            ssh -o BatchMode=yes $HostAlias "mkdir -p '$remoteDir'"
        }
        scp -o BatchMode=yes -o ConnectTimeout=20 $local "${HostAlias}:$remote"
        if ($LASTEXITCODE -ne 0) { throw "scp failed: $rel" }
        Write-Host "synced ${HostAlias}: $rel"
    }
}

function Resolve-DomesticPaperLocal([string]$ProjectRoot) {
    $manifest = Join-Path $ProjectRoot "scripts\domestic_paper_manifest.txt"
    if (Test-Path -LiteralPath $manifest) {
        $name = (Get-Content -LiteralPath $manifest -Encoding UTF8 | Where-Object { $_.Trim() } | Select-Object -First 1).Trim()
        $candidate = Join-Path $ProjectRoot "remote_domestic_optimize\$name"
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }
    $fallback = Get-ChildItem -LiteralPath (Join-Path $ProjectRoot "remote_domestic_optimize") -Filter "*.py" |
        Where-Object { $_.Name -match "模拟实盘" } |
        Select-Object -First 1
    if ($fallback) { return $fallback.FullName }
    throw "domestic paper script not found under remote_domestic_optimize"
}

function Verify-Import([string]$HostAlias, [string]$RemoteRoot, [string]$PyExe, [string]$PyPrefix) {
    try {
        if ($HostAlias -eq "overseas-quant") {
            ssh -o BatchMode=yes $HostAlias "cd $RemoteRoot && PYTHONPATH=src:packages/fengji_core $PyExe -c 'import fengji_core.feishu_trade_notify; import fengji_feishu_paper_notify; print(1)'"
        } else {
            ssh -o BatchMode=yes $HostAlias "powershell -NoProfile -Command `"Set-Location '$RemoteRoot'; `$env:PYTHONPATH='src;packages/fengji_core'; & python -c 'import fengji_core.feishu_trade_notify; import fengji_feishu_paper_notify; print(1)'`""
        }
        if ($LASTEXITCODE -ne 0) { throw "import exit $LASTEXITCODE" }
        Write-Host "import ok on $HostAlias"
    } catch {
        Write-Host "import check skipped/warn on ${HostAlias}: $_" -ForegroundColor Yellow
    }
}

if (-not $DomesticOnly) {
    Write-Host "=== Overseas ===" -ForegroundColor Cyan
    Sync-List "overseas-quant" "/home/ubuntu/quant_crypto" ($shared + $overseasExtra)
    Verify-Import "overseas-quant" "/home/ubuntu/quant_crypto" ".venv/bin/python" "PYTHONPATH=src:packages/fengji_core"
    ssh -o BatchMode=yes overseas-quant "cd /home/ubuntu/quant_crypto && pkill -f 'src/fengji_pending_order_monitor.py' 2>/dev/null || true; pkill -f 'src/overseas_paper_monitor.py' 2>/dev/null || true; bash scripts/watchdog_overseas.sh 2>&1 | tail -10"
    ssh -o BatchMode=yes overseas-quant "pgrep -af 'fengji_pending_order_monitor.py|overseas_paper_monitor.py' | grep -v pgrep || true"
}

if (-not $OverseasOnly) {
    Write-Host "=== Domestic ===" -ForegroundColor Cyan
    Sync-List "domestic-quant" "C:/Users/Administrator/quant_futures" ($shared + $domesticExtra)
    Deploy-DomesticPaper $root
    Verify-Import "domestic-quant" "C:/Users/Administrator/quant_futures" "python" ""
    scp -o BatchMode=yes scripts/restart_domestic_pending_monitor.ps1 domestic-quant:C:/Users/Administrator/quant_futures/scripts/
    scp -o BatchMode=yes scripts/restart_domestic_paper_only.ps1 domestic-quant:C:/Users/Administrator/quant_futures/scripts/
    ssh -o BatchMode=yes domestic-quant "powershell -NoProfile -ExecutionPolicy Bypass -File C:/Users/Administrator/quant_futures/scripts/restart_domestic_pending_monitor.ps1"
    ssh -o BatchMode=yes domestic-quant "powershell -NoProfile -ExecutionPolicy Bypass -File C:/Users/Administrator/quant_futures/scripts/restart_domestic_paper_only.ps1"
    ssh -o BatchMode=yes domestic-quant "powershell -NoProfile -ExecutionPolicy Bypass -File C:/Users/Administrator/quant_futures/scripts/watchdog_domestic.ps1" | Select-Object -Last 12
}

Write-Host "=== Done ===" -ForegroundColor Green
