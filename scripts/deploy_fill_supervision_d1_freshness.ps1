# Sync fill_supervision D1 freshness fix to overseas + domestic (audit layer; no strategy change)
param(
    [string]$OverseasHost = "overseas-quant",
    [string]$OverseasRoot = "/home/ubuntu/quant_crypto",
    [string]$DomesticHost = "domestic-quant",
    [string]$DomesticRoot = "C:/Users/Administrator/quant_futures"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root
$rel = "packages/fengji_core/fengji_core/fill_supervision.py"
$local = Join-Path $root ($rel -replace "/", "\")

Write-Host "=== pytest fill_supervision ===" -ForegroundColor Cyan
python -m pytest (Join-Path $root "tests\test_fill_supervision.py") -q
if ($LASTEXITCODE -ne 0) { throw "pytest failed" }

foreach ($pair in @(
        @{ Host = $OverseasHost; Root = $OverseasRoot },
        @{ Host = $DomesticHost; Root = $DomesticRoot }
    )) {
    $remote = "$($pair.Root)/$($rel -replace '\\','/')"
    Write-Host "=== sync $($pair.Host) ===" -ForegroundColor Cyan
    scp -o BatchMode=yes -o ConnectTimeout=25 $local "$($pair.Host):$remote"
    if ($LASTEXITCODE -ne 0) { throw "scp failed: $($pair.Host)" }
}

Write-Host "=== verify overseas hash ===" -ForegroundColor Cyan
python (Join-Path $root "scripts\compare_overseas_core_hashes.py")
if ($LASTEXITCODE -ne 0) { throw "overseas hash mismatch" }

Write-Host "=== verify domestic hash ===" -ForegroundColor Cyan
$verifyPy = @'
import hashlib, json, sys
from pathlib import Path
root = Path(r"C:/Users/Administrator/quant_futures")
p = root / "packages/fengji_core/fengji_core/fill_supervision.py"
print(json.dumps({"fill_supervision_md5": hashlib.md5(p.read_bytes()).hexdigest()[:16]}))
sys.path[:0] = [str(root / "src"), str(root / "packages" / "fengji_core")]
from fengji_core.fill_supervision import resolve_d1_csv
print("import_ok")
'@
$tmp = Join-Path $env:TEMP "verify_domestic_fill_supervision.py"
Set-Content -Path $tmp -Value $verifyPy -Encoding UTF8
scp -o BatchMode=yes $tmp "${DomesticHost}:$DomesticRoot/scripts/_verify_domestic_fill_supervision.py"
ssh -o BatchMode=yes $DomesticHost "python $DomesticRoot/scripts/_verify_domestic_fill_supervision.py"

Write-Host "=== Done ===" -ForegroundColor Green
