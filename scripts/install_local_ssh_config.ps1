# 本机一键：生成峰极 SSH 密钥 + 写入 %USERPROFILE%\.ssh\config（合并 domestic-quant / overseas-quant）
param(
    [switch]$ForceConfig
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$sshDir = Join-Path $env:USERPROFILE ".ssh"
$user = $env:USERNAME

if (-not (Test-Path $sshDir)) {
    New-Item -ItemType Directory -Path $sshDir -Force | Out-Null
}

& (Join-Path $root "scripts\setup_ssh_passwordless.ps1") -Target both -SshDir $sshDir

$domesticKey = "C:/Users/$user/.ssh/quant_domestic_ed25519"
$overseasKey = "C:/Users/$user/.ssh/quant_overseas_ed25519"

$configBlock = @"

# --- FengJi quant (auto by install_local_ssh_config.ps1) ---
Host domestic-quant fengji-domestic 106.53.107.248
    HostName 106.53.107.248
    User Administrator
    IdentityFile $domesticKey
    IdentitiesOnly yes
    StrictHostKeyChecking accept-new

Host overseas-quant fengji-overseas 43.167.10.79
    HostName 43.167.10.79
    User ubuntu
    IdentityFile $overseasKey
    IdentitiesOnly yes
    StrictHostKeyChecking accept-new
"@

$configPath = Join-Path $sshDir "config"
if (-not (Test-Path $configPath)) {
    Set-Content -Path $configPath -Value $configBlock.TrimStart() -Encoding utf8
    Write-Host "Created $configPath" -ForegroundColor Green
} elseif ($ForceConfig -or -not (Select-String -Path $configPath -Pattern "domestic-quant" -Quiet)) {
    Add-Content -Path $configPath -Value "`n$configBlock" -Encoding utf8
    Write-Host "Appended FengJi hosts to $configPath" -ForegroundColor Green
} else {
    Write-Host "Config already contains domestic-quant; skip (use -ForceConfig to append again)" -ForegroundColor DarkGray
}

Write-Host "`nNext (one-time, will prompt server password):" -ForegroundColor Cyan
Write-Host "  Get-Content `"$sshDir\quant_overseas_ed25519.pub`" | ssh ubuntu@43.167.10.79 `"mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys`""
Write-Host "  Get-Content `"$sshDir\quant_domestic_ed25519.pub`" | ssh Administrator@106.53.107.248 `"powershell -NoProfile -Command `"`$d='C:\Users\Administrator\.ssh'; New-Item -ItemType Directory -Force -Path `$d | Out-Null; Get-Content - | Add-Content -Path (Join-Path `$d 'authorized_keys')`"`""
Write-Host "`nVerify: .\scripts\ssh_test_servers.ps1" -ForegroundColor Cyan
