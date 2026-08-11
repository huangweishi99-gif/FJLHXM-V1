# Verify remote domestic paper deployment (runs commands ON domestic-quant)
$ErrorActionPreference = "Stop"
$remotePs = @'
$r = 'C:/Users/Administrator/quant_futures'
Write-Output '--- manifest ---'
if (Test-Path "$r/scripts/domestic_paper_manifest.txt") {
  Get-Content "$r/scripts/domestic_paper_manifest.txt" -Encoding UTF8
} else { Write-Output 'MISSING manifest' }
Write-Output '--- py files in root ---'
Get-ChildItem $r -Filter '*.py' | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize | Out-String
$n = (Get-Content "$r/scripts/domestic_paper_manifest.txt" -Encoding UTF8 -ErrorAction SilentlyContinue | Select-Object -First 1)
if ($n) {
  $n = $n.Trim()
  $p = Join-Path $r $n
  Write-Output "paper=$p exists=$(Test-Path -LiteralPath $p)"
  if (Test-Path -LiteralPath $p) {
    Select-String -LiteralPath $p -Pattern 'notify_paper_open|feishu_paper_notify' | Select-Object -First 5 | ForEach-Object { $_.Line.Trim() }
  }
}
Write-Output '--- python processes ---'
Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" | ForEach-Object { "$($_.ProcessId) $($_.CommandLine)" }
'@
$remotePs | ssh -o BatchMode=yes domestic-quant "powershell -NoProfile -Command -"
