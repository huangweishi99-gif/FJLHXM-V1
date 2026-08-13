Set-Location "C:\Users\Administrator\quant_futures"
$env:PYTHONPATH = "src;packages\fengji_core"
$ids = (Get-Content "runtime\m5_b_domestic_ids.txt" -Raw).Trim()
& py -3 scripts\repair_corrupt_futures_state_from_audit.py `
  --audit runtime\m5_empty_audit.json `
  --state runtime\state_futures_v2.json `
  --monitor-state runtime\fengji_pending_orders\state.json `
  --order-id $ids `
  --reason "M5 B zone DS01 dry-run" `
  --out runtime\m5_b_zone_repair_domestic_dryrun.json
exit $LASTEXITCODE
