# 测试 ~/.ssh/config 中 domestic-quant / overseas-quant 免密连通
$ErrorActionPreference = "Stop"

$hosts = @(
    @{ Name = "domestic-quant"; Label = "国内" },
    @{ Name = "overseas-quant"; Label = "国外" }
)

$failed = 0
foreach ($h in $hosts) {
    Write-Host "`n[$($h.Label)] ssh $($h.Name) ..." -ForegroundColor Cyan
    $out = ssh -o BatchMode=yes -o ConnectTimeout=15 $h.Name "echo SSH_OK" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAIL: $out" -ForegroundColor Red
        $failed++
        continue
    }
    Write-Host "OK: $out" -ForegroundColor Green
}

if ($failed -gt 0) {
    Write-Host "`n有 $failed 台未通过。请运行 .\scripts\setup_ssh_passwordless.ps1 并按提示安装公钥。" -ForegroundColor Yellow
    exit 1
}

Write-Host "`n两台服务器免密 SSH 正常。" -ForegroundColor Green
