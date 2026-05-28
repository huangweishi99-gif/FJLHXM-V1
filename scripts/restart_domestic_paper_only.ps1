# 仅重启国内期货/A股模拟盘（FENGJI_FEISHU_WEBHOOK 来自 runtime/feishu_webhook.env）
$ErrorActionPreference = "Stop"
$root = "C:\Users\Administrator\quant_futures"
$py = "C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"
. (Join-Path $PSScriptRoot "load_feishu_webhook.ps1")
$hook = Get-FeishuWebhook -Root $root
if (-not $hook) {
    Write-Warning "No webhook in env file — Feishu notifications disabled until runtime/feishu_webhook.env is set"
}

Set-Location $root

$paperItem = Get-ChildItem -File -Filter "*.py" | Where-Object { $_.Name -match "01-08" -and $_.Name -notmatch "Dash" } | Select-Object -First 1
if (-not $paperItem) {
    $paperItem = Get-ChildItem -File "*.py" | Where-Object { $_.Length -gt 15000 } | Sort-Object Length -Descending | Select-Object -First 1
}
if (-not $paperItem) { throw "Domestic paper script not found under $root" }
$paper = $paperItem.FullName
$paperLeaf = $paperItem.Name
Write-Host "Using paper script: $paperLeaf"

Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -match [regex]::Escape($paperLeaf) -or $_.CommandLine -match "01-08"
} | ForEach-Object {
    try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop } catch {}
}
Start-Sleep -Seconds 2

$hookSet = if ($hook) { "set `"FENGJI_FEISHU_WEBHOOK=$hook`"&& " } else { "" }
$cmd = "cmd.exe /d /c cd /d `"$root`" && set PYTHONPATH=src;packages/fengji_core&& set PYTHONIOENCODING=utf-8&& set PYTHONUTF8=1&& ${hookSet}`"$py`" -u `"$paper`" >> `"runtime\logs\paper_futures_run.log`" 2>> `"runtime\logs\paper_futures_err.log`""
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd; CurrentDirectory = $root }
Write-Host "Create ReturnValue=$($r.ReturnValue) PID=$($r.ProcessId)"
Start-Sleep -Seconds 4
$found = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match [regex]::Escape($paperLeaf) -or ($_.CommandLine -match "01-08" -and $_.CommandLine -match "\.py") })
if (-not $found) {
    Write-Host "WARN: paper process not visible yet; check runtime\logs\paper_futures_err.log"
    if (Test-Path "$root\runtime\logs\paper_futures_err.log") { Get-Content "$root\runtime\logs\paper_futures_err.log" -Tail 5 }
    exit 2
}
foreach ($p in $found) {
    $ok = if ($p.CommandLine -match "feishu-webhook\s+`"https://") { "WARN_CMDLINE_WEBHOOK" } else { "OK" }
    Write-Host "Paper PID=$($p.ProcessId) $ok (env FENGJI_FEISHU_WEBHOOK=$(if ($hook) { 'set' } else { 'empty' }))"
}
