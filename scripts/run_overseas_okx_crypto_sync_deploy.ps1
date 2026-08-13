param(
    [switch]$DeployOnly,
    [switch]$SyncOnly
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$SshHost = "overseas-quant"
$remote = "/home/ubuntu/quant_crypto"

Set-Location $root

$files = @(
    @{ Local = "data_manager.py"; Remote = "$remote/data_manager.py" },
    @{ Local = "scripts/sync_missing_crypto_15m.py"; Remote = "$remote/scripts/sync_missing_crypto_15m.py" },
    @{ Local = "scripts/watchdog_overseas.sh"; Remote = "$remote/scripts/watchdog_overseas.sh" },
    @{ Local = "packages/fengji_core/fengji_core/fill_supervision.py"; Remote = "$remote/packages/fengji_core/fengji_core/fill_supervision.py" }
)

if (-not $SyncOnly) {
    Write-Host "[deploy] overseas OKX + fill_supervision files..."
    foreach ($f in $files) {
        $src = Join-Path $root $f.Local
        scp -o BatchMode=yes $src "${SshHost}:$($f.Remote)"
        Write-Host "  ok $($f.Local)"
    }
}

if (-not $DeployOnly) {
    Write-Host "[sync] HYPE/ATH M15+D1+H1 via OKX..."
    $syncCmd = "cd $remote && export PYTHONPATH=src:packages/fengji_core:services:scripts && .venv/bin/python scripts/sync_missing_crypto_15m.py --symbols HYPEUSDT,ATHUSDT --timeframes M15,D1,H1 --force-okx --fix-os --root $remote && echo '--- ATH D1 ---' && tail -2 data/1d/ATHUSDT.csv && echo '--- HYPE D1 ---' && tail -2 data/1d/HYPEUSDT.csv"
    ssh -o BatchMode=yes $SshHost $syncCmd
    Write-Host "[verify] overseas fill_supervision 72h..."
    $auditCmd = "cd $remote && export PYTHONPATH=src:packages/fengji_core:services:scripts && .venv/bin/python scripts/audit_paper_fills.py --root $remote --profile overseas --since-hours 72 --fail-on-invalid --ack-file runtime/fill_supervision_acknowledged.json --quiet; echo FILL_AUDIT_EXIT=`$?"
    ssh -o BatchMode=yes $SshHost $auditCmd
}

Write-Host "done run_overseas_okx_crypto_sync_deploy.ps1"
