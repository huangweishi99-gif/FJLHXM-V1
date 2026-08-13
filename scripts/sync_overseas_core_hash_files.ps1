param(
    [string]$SshHost = "overseas-quant",
    [string]$RemoteRoot = "/home/ubuntu/quant_crypto"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

$files = @(
    "src/fengji_pending_order_monitor.py",
    "src/fengji_feishu_notify.py",
    "src/fengji_total_radar.py",
    "src/overseas_paper_monitor.py",
    "packages/fengji_core/fengji_core/ds03_pending_fill.py",
    "packages/fengji_core/fengji_core/stop_bar_monitor.py",
    "packages/fengji_core/fengji_core/ds08_pending_fill.py",
    "src/fengji_futures_pending_order_monitor.py",
    "packages/fengji_core/fengji_core/fill_supervision.py",
    "packages/fengji_core/fengji_core/feishu_trade_notify.py",
    "data_manager.py",
    "services/crypto_ingest.py",
    "scripts/sync_missing_crypto_15m.py",
    "scripts/check_okx_csv_freshness.py",
    "scripts/check_ds09_feishu_dedup_state.py",
    "scripts/watchdog_overseas.sh",
    "scripts/audit_new10_crypto_fills.py"
)

foreach ($rel in $files) {
    $local = Join-Path $root ($rel -replace "/", "\")
    if (-not (Test-Path -LiteralPath $local)) {
        Write-Warning "skip missing: $local"
        continue
    }
    $remote = "$RemoteRoot/$($rel -replace '\\','/')"
    scp -o BatchMode=yes -o ConnectTimeout=20 $local "${SshHost}:$remote"
    if ($LASTEXITCODE -ne 0) { throw "scp failed: $rel" }
    Write-Host "synced $rel"
}

python (Join-Path $root "scripts\compare_overseas_core_hashes.py")
exit $LASTEXITCODE
