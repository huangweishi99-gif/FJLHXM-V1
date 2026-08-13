# Sync DS08 entry_fill execution layer to domestic futures + restart pending monitor
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root
$remote = "C:/Users/Administrator/quant_futures"

$files = @(
    "packages/fengji_core/fengji_core/ds08_pending_fill.py",
    "src/fengji_futures_pending_order_monitor.py"
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

Write-Host "=== restart pending monitor ===" -ForegroundColor Cyan
scp -o BatchMode=yes scripts/restart_domestic_pending_monitor.ps1 "domestic-quant:$remote/scripts/"
ssh -o BatchMode=yes domestic-quant "powershell -NoProfile -ExecutionPolicy Bypass -File $remote/scripts/restart_domestic_pending_monitor.ps1"

Write-Host "=== verify hashes + import ===" -ForegroundColor Cyan
$verifyPy = @'
import hashlib, json, sys
from pathlib import Path
root = Path(r"C:/Users/Administrator/quant_futures")
files = [
    "packages/fengji_core/fengji_core/ds08_pending_fill.py",
    "src/fengji_futures_pending_order_monitor.py",
]
out = {}
for rel in files:
    p = root / rel.replace("/", "\\")
    h = hashlib.md5(p.read_bytes()).hexdigest()[:16]
    out[rel] = h
sys.path[:0] = [str(root / "src"), str(root / "packages" / "fengji_core")]
from fengji_core.ds08_pending_fill import resolve_ds08_pending_fill
out["import_ok"] = bool(resolve_ds08_pending_fill)
print(json.dumps(out, ensure_ascii=False))
'@
$tmp = Join-Path $env:TEMP "verify_domestic_ds08.py"
Set-Content -Path $tmp -Value $verifyPy -Encoding UTF8
scp -o BatchMode=yes $tmp "domestic-quant:$remote/scripts/_verify_domestic_ds08.py"
ssh -o BatchMode=yes domestic-quant "python $remote/scripts/_verify_domestic_ds08.py"

Write-Host "=== Done ===" -ForegroundColor Green
