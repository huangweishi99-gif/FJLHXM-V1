# 从本机用户环境变量 TQ_PHONE/TQ_PASS 同步到国内服务器（不写进仓库）。
$ErrorActionPreference = "Stop"
$phone = [Environment]::GetEnvironmentVariable("TQ_PHONE", "User")
$pass = [Environment]::GetEnvironmentVariable("TQ_PASS", "User")
if (-not $phone -or -not $pass) {
    throw "本机未设置 TQ_PHONE/TQ_PASS 用户环境变量，请先在 Windows 环境变量里配置。"
}
$RemoteHost = "domestic-quant"
$remoteScript = @"
[Environment]::SetEnvironmentVariable('TQ_PHONE', '$($phone.Replace("'", "''"))', 'User')
[Environment]::SetEnvironmentVariable('TQ_PASS', '$($pass.Replace("'", "''"))', 'User')
Write-Host 'domestic TQ env updated (User scope)'
"@
$encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($remoteScript))
Write-Host "Sync TQ credentials to $RemoteHost ..." -ForegroundColor Cyan
ssh -o BatchMode=yes $RemoteHost "powershell -NoProfile -EncodedCommand $encoded"
Write-Host "Done." -ForegroundColor Green
