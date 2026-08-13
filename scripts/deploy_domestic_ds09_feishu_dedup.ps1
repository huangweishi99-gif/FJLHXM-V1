# DS09 预计挂单飞书去重 + 稳定 setup_key：同步国内期货雷达/挂单监控依赖
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root
$remote = "C:/Users/Administrator/quant_futures"

$files = @(
    "src/fengji_feishu_notify.py",
    "src/fengji_pending_order_monitor.py",
    "src/fengji_total_radar.py"
)

foreach ($rel in $files) {
    $local = Join-Path $root ($rel -replace "/", "\")
    if (-not (Test-Path -LiteralPath $local)) { throw "missing: $local" }
    $dest = "$remote/$($rel -replace '\\','/')"
    $destDir = ($dest -replace '/[^/]+$', '')
    ssh -o BatchMode=yes domestic-quant "if (-not (Test-Path '$destDir')) { New-Item -ItemType Directory -Force -Path '$destDir' | Out-Null }"
    scp -o BatchMode=yes -o ConnectTimeout=30 $local "domestic-quant:$dest"
    Write-Host "synced: $rel"
}

Write-Host "=== restart domestic pending monitor ===" -ForegroundColor Cyan
scp -o BatchMode=yes scripts/restart_domestic_pending_monitor.ps1 "domestic-quant:$remote/scripts/"
ssh -o BatchMode=yes domestic-quant "powershell -NoProfile -ExecutionPolicy Bypass -File $remote/scripts/restart_domestic_pending_monitor.ps1"

Write-Host "=== verify imports ===" -ForegroundColor Cyan
$verifyPy = @'
import json, sys
from pathlib import Path
root = Path(r"C:/Users/Administrator/quant_futures")
sys.path[:0] = [str(root / "src"), str(root / "packages" / "fengji_core")]
from fengji_feishu_notify import pending_semantic_notify_key, pending_setup_notify_key
from fengji_total_radar import add_ds09
from fengji_pending_order_monitor import notify_new_pending_orders
print(json.dumps({
    "pending_setup_notify_key": pending_setup_notify_key("X|DS09|LONG|d|lock=1|def=2|1.0"),
    "pending_semantic_notify_key": pending_semantic_notify_key({
        "symbol": "X", "strategy_id": "DS09", "timeframe": "M15", "side": "long",
        "trigger_price": 1.0, "stop_price": 0.9,
    }),
    "import_ok": True,
}, ensure_ascii=False))
'@
$tmp = Join-Path $env:TEMP "verify_domestic_ds09_dedup.py"
Set-Content -Path $tmp -Value $verifyPy -Encoding UTF8
scp -o BatchMode=yes $tmp "domestic-quant:$remote/scripts/_verify_domestic_ds09_dedup.py"
ssh -o BatchMode=yes domestic-quant "python $remote/scripts/_verify_domestic_ds09_dedup.py"

Write-Host "=== Done ===" -ForegroundColor Green
