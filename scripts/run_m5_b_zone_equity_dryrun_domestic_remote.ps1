Set-Location "C:\Users\Administrator\quant_futures"
$env:PYTHONPATH = "src;packages\fengji_core"
$state = "runtime/fengji_futures/state_futures_v2.json"
$ids = @(
  "ECUSDT-DS01-D1-long-2dfeae944abdef49",
  "ECUSDT-DS01-D1-long-f48041169975e929",
  "LHUSDT-DS01-D1-short-58b2638967b67a32",
  "LHUSDT-DS01-D1-long-50754f2091ac9227"
)
$rows = @()
foreach ($oid in $ids) {
  Write-Host "==== $oid ===="
  $out = & py -3 scripts/apply_equity_rollback.py --state $state --order-id $oid --dry-run 2>&1
  Write-Host $out
  $rows += [pscustomobject]@{ order_id = $oid; output = ($out | Out-String).Trim() }
}
$payload = @{
  generated_at = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
  note = "dry-run only; no equity applied"
  rows = $rows
}
$payload | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 "runtime/m5_b_zone_equity_dryrun_domestic.json"
