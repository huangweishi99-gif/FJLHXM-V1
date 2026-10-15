# Run ON domestic server: 诊断 events.jsonl 无法追加写入（OSError Errno 22）
$root = "C:\Users\Administrator\quant_futures"
Set-Location $root
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$dir = Join-Path $root "runtime\fengji_pending_orders"
$target = Join-Path $dir "events.jsonl"

Write-Host "=== DIR ==="
if (Test-Path -LiteralPath $dir) {
    Write-Host ("dir exists, items=" + (Get-ChildItem -LiteralPath $dir).Count)
    Get-ChildItem -LiteralPath $dir | Sort-Object Length -Descending | Select-Object -First 10 Name, Length, Attributes, LastWriteTime | Format-Table -AutoSize
} else { Write-Host "dir missing" }

Write-Host "=== TARGET FILE ==="
if (Test-Path -LiteralPath $target) {
    $fi = Get-Item -LiteralPath $target -Force
    Write-Host ("name=[" + $fi.Name + "] len=" + $fi.Length + " attr=" + $fi.Attributes + " mtime=" + $fi.LastWriteTime)
    Write-Host ("isdir=" + ($fi.PSIsContainer) + " ext=[" + $fi.Extension + "]")
} else { Write-Host "file missing (will be created)" }

Write-Host "=== .NET APPEND TEST ==="
try {
    $fs = [System.IO.File]::Open($target, [System.IO.FileMode]::Append, [System.IO.FileAccess]::Write, [System.IO.FileShare]::ReadWrite)
    $fs.Close()
    Write-Host "DOTNET_APPEND_OK"
} catch {
    Write-Host ("DOTNET_APPEND_FAIL: " + $_.Exception.GetType().FullName + " :: " + $_.Exception.Message)
}

Write-Host "=== PYTHON APPEND TEST ==="
$py = "C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"
$code = @'
import sys, traceback
from pathlib import Path
p = Path(r"C:\Users\Administrator\quant_futures\runtime\fengji_pending_orders\events.jsonl")
print("exists", p.exists(), "isdir", p.is_dir())
try:
    print("size", p.stat().st_size)
except Exception as e:
    print("stat fail", e)
try:
    with p.open("a", encoding="utf-8") as h:
        h.write("")
    print("PY_APPEND_OK")
except Exception:
    traceback.print_exc()
try:
    with p.open("r", encoding="utf-8") as h:
        h.read(100)
    print("PY_READ_OK")
except Exception as e:
    print("PY_READ_FAIL", e)
'@
$tmp = Join-Path $root "runtime\_diag_events_open.py"
Set-Content -LiteralPath $tmp -Value $code -Encoding UTF8
& $py $tmp
Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue

Write-Host "=== DISK ==="
Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Name -in @("C") } | ForEach-Object {
    Write-Host ("C used=" + [math]::Round($_.Used / 1GB, 2) + "GB free=" + [math]::Round($_.Free / 1GB, 2) + "GB")
}
