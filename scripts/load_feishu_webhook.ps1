param(
    [string]$ProjectRoot = "C:\Users\Administrator\quant_futures"
)

function Get-FeishuWebhook {
    param([string]$Root = $ProjectRoot)
    foreach ($name in @("FENGJI_FEISHU_WEBHOOK", "FEISHU_WEBHOOK")) {
        $v = [Environment]::GetEnvironmentVariable($name)
        if ($v) { return $v.Trim() }
    }
    $file = Join-Path $Root "runtime\feishu_webhook.env"
    if (-not (Test-Path $file)) { return "" }
    foreach ($line in Get-Content $file -Encoding UTF8) {
        $t = $line.Trim()
        if (-not $t -or $t.StartsWith("#")) { continue }
        if ($t -match '^(?:FEISHU_WEBHOOK|FENGJI_FEISHU_WEBHOOK)\s*=\s*(.+)$') {
            return $Matches[1].Trim().Trim('"').Trim("'")
        }
    }
    return ""
}
