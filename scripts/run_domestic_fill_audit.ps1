# Run on domestic-quant server (remote).
Set-Location "C:\Users\Administrator\quant_futures"
$env:PYTHONPATH = "src;packages\fengji_core"
$args = @(
    "scripts\audit_paper_fills.py",
    "--profile", "domestic",
    "--since-hours", "720",
    "--fail-on-invalid"
)
& py -3 @args
exit $LASTEXITCODE
