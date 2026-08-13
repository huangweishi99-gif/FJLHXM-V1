Set-Location "C:\Users\Administrator\quant_futures"
$env:PYTHONPATH = "src;packages\fengji_core"
$ids = @(
  "BRUSDT-DS03-D1-short-d22b86c84c29934d",
  "EBUSDT-DS03-D1-short-026953b4e1f90203",
  "EGUSDT-DS03-D1-short-a263483ed8822ffe",
  "SHUSDT-DS03-D1-short-d9d569ed33cf4830",
  "ECUSDT-DS03-D1-long-8f2d0fe7f72adafa",
  "JDUSDT-DS03-D1-long-2a735611bdec0d36",
  "AGUSDT-DS03-D1-short-bf027508038fcd5a",
  "AUUSDT-DS03-D1-short-fa25bfd2f7e290eb",
  "ECUSDT-DS03-D1-long-e666c869fab24219",
  "EBUSDT-DS03-D1-short-68d21c33a12d2f98"
) -join ","
$reason = "M5 A zone DS03 audit_invalid user approved 2026-06-10"
& py -3 scripts\repair_corrupt_futures_state_from_audit.py `
  --audit runtime\m5_empty_audit.json `
  --state runtime\state_futures_v2.json `
  --monitor-state runtime\fengji_pending_orders\state.json `
  --order-id $ids `
  --reason $reason `
  --out runtime\m5_a_zone_repair_domestic_dryrun.json
exit $LASTEXITCODE
