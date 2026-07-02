# Verify remote personal WeChat payment deploy (via SSH tunnel)
param(
    [string]$SshHost = "domestic-quant",
    [int]$LocalPort = 8046
)

$ErrorActionPreference = "Stop"
$tunnel = Start-Process ssh -ArgumentList @("-o", "BatchMode=yes", "-N", "-L", "${LocalPort}:127.0.0.1:8000", $SshHost) -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 4
try {
    $base = "http://127.0.0.1:$LocalPort"
    $cfg = Invoke-RestMethod "$base/api/v1/subscriptions/payment-config" -TimeoutSec 15
    $html = Invoke-WebRequest "$base/web/payment.html?pay=standard" -TimeoutSec 15 -UseBasicParsing
    $js = Invoke-WebRequest "$base/web/js/app.js" -TimeoutSec 15 -UseBasicParsing
    $ok = ($cfg.pricing.standard.amount_yuan -eq 99) -and
          ($cfg.pricing.pro.amount_yuan -eq 299) -and
          ($cfg.channel_mode -eq "personal_wechat_qr") -and
          ($html.Content -match "payAmountLine") -and
          ($js.Content -match 'typeof resOrResult\.json === "function"')
    Write-Host "REMOTE_PERSONAL_WECHAT_PAY_VERIFY ok=$ok channel=$($cfg.channel_mode) standard=$($cfg.pricing.standard.amount_yuan) pro=$($cfg.pricing.pro.amount_yuan)"
    if (-not $ok) { exit 1 }
}
finally {
    if ($tunnel -and -not $tunnel.HasExited) { Stop-Process -Id $tunnel.Id -Force -ErrorAction SilentlyContinue }
}
