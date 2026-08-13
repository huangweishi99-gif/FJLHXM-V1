# Upload domestic paper monitor with UTF-8 filename via ASCII temp path
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$manifest = Join-Path $root "scripts\domestic_paper_manifest.txt"
$name = (Get-Content -LiteralPath $manifest -Encoding UTF8 | Where-Object { $_.Trim() } | Select-Object -First 1).Trim()
$local = Join-Path $root "remote_domestic_optimize\$name"
if (-not (Test-Path -LiteralPath $local)) { throw "missing local paper: $local" }

$tmpRemote = "C:/Users/Administrator/quant_futures/runtime/_deploy_domestic_paper_tmp.py"
scp -o BatchMode=yes -o ConnectTimeout=30 $local "domestic-quant:$tmpRemote"
$remotePs = @'
$r = 'C:/Users/Administrator/quant_futures'
$n = (Get-Content "$r/scripts/domestic_paper_manifest.txt" -Encoding UTF8 | Select-Object -First 1).Trim()
Copy-Item "$r/runtime/_deploy_domestic_paper_tmp.py" (Join-Path $r $n) -Force
Remove-Item "$r/runtime/_deploy_domestic_paper_tmp.py" -Force
Write-Output "deployed $n"
'@
$remotePs | ssh -o BatchMode=yes domestic-quant "powershell -NoProfile -Command -"
ssh -o BatchMode=yes domestic-quant "powershell -NoProfile -ExecutionPolicy Bypass -File C:/Users/Administrator/quant_futures/scripts/watchdog_domestic.ps1" | Select-Object -Last 8
