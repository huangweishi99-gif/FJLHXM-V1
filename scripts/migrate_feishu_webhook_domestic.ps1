# 一次性：从正在运行的进程命令行提取 webhook 写入 runtime/feishu_webhook.env（不回显 URL）
$ErrorActionPreference = "Stop"
$root = "C:\Users\Administrator\quant_futures"
$dest = Join-Path $root "runtime\feishu_webhook.env"

if (Test-Path $dest) {
    Write-Host "feishu_webhook.env already exists — skip migrate"
    exit 0
}

$proc = Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -match "feishu-webhook" } |
    Select-Object -First 1

if (-not $proc) {
    Write-Host "No running process with --feishu-webhook; create runtime/feishu_webhook.env manually"
    exit 1
}

if ($proc.CommandLine -match '--feishu-webhook\s+"([^"]+)"') {
    New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
    "FEISHU_WEBHOOK=$($Matches[1])" | Set-Content -Path $dest -Encoding utf8
    Write-Host "Migrated webhook to runtime/feishu_webhook.env (URL not printed)"
    exit 0
}

Write-Host "Could not parse webhook from process command line"
exit 1
