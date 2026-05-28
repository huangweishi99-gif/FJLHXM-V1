Set-Location "C:\Users\Administrator\quant_futures"
"--- DS05 radar rows ---"
if (Test-Path runtime\fengji_radar\radar.csv) {
    Select-String -Path runtime\fengji_radar\radar.csv -Pattern "DS05" | Select-Object -First 10 | ForEach-Object { $_.Line }
}
