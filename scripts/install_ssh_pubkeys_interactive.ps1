# 一次性安装本机公钥到国内/海外服务器（会提示输入服务器密码，各一次）
param(
    [ValidateSet("both", "domestic", "overseas")]
    [string]$Target = "both"
)

$ErrorActionPreference = "Stop"
$sshDir = Join-Path $env:USERPROFILE ".ssh"
$domesticHost = "Administrator@106.53.107.248"
$overseasHost = "ubuntu@43.167.10.79"

function Install-OverseasPubKey {
    $pub = Join-Path $sshDir "quant_overseas_ed25519.pub"
    if (-not (Test-Path $pub)) { throw "Missing $pub" }
    $remoteTmp = "/home/ubuntu/.ssh/fengji_install.pub"
    Write-Host "[overseas] $overseasHost — scp 公钥 + 写入 authorized_keys（最多输入 2 次密码）" -ForegroundColor Cyan
    ssh -o StrictHostKeyChecking=accept-new $overseasHost "mkdir -p ~/.ssh && chmod 700 ~/.ssh"
    scp -o StrictHostKeyChecking=accept-new $pub "${overseasHost}:$remoteTmp"
    ssh -o StrictHostKeyChecking=accept-new $overseasHost @'
bash -lc 'set -e; k=$(cat ~/.ssh/fengji_install.pub); touch ~/.ssh/authorized_keys; chmod 600 ~/.ssh/authorized_keys; grep -qxF "$k" ~/.ssh/authorized_keys || echo "$k" >> ~/.ssh/authorized_keys; rm -f ~/.ssh/fengji_install.pub; echo OVERSEAS_PUBKEY_OK'
'@
}

function Install-DomesticPubKey {
    $pub = Join-Path $sshDir "quant_domestic_ed25519.pub"
    if (-not (Test-Path $pub)) { throw "Missing $pub" }
    $remoteTmp = "C:/Users/Administrator/.ssh/fengji_install.pub"
    Write-Host "[domestic] $domesticHost — scp 公钥 + 写入 authorized_keys（最多输入 2 次密码）" -ForegroundColor Cyan
    scp -o StrictHostKeyChecking=accept-new $pub "${domesticHost}:$remoteTmp"
    # 外层单引号：避免本地 PowerShell 展开 $d；内层双引号供远端 PowerShell 使用
    $remoteCmd = @'
powershell -NoProfile -Command "New-Item -ItemType Directory -Force -Path C:/Users/Administrator/.ssh | Out-Null; $k=(Get-Content C:/Users/Administrator/.ssh/fengji_install.pub -Raw).Trim(); $ua='C:/Users/Administrator/.ssh/authorized_keys'; $aa='C:/ProgramData/ssh/administrators_authorized_keys'; if (-not (Test-Path $ua) -or (Get-Content $ua -Raw) -notlike ('*'+$k+'*')) { Add-Content -Path $ua -Value $k }; if (-not (Test-Path $aa)) { New-Item -ItemType File -Force -Path $aa | Out-Null }; if ((Get-Content $aa -Raw -ErrorAction SilentlyContinue) -notlike ('*'+$k+'*')) { Add-Content -Path $aa -Value $k }; Remove-Item C:/Users/Administrator/.ssh/fengji_install.pub -Force -ErrorAction SilentlyContinue; Write-Output DOMESTIC_PUBKEY_OK"
'@
    ssh -o StrictHostKeyChecking=accept-new $domesticHost $remoteCmd
}

if ($Target -in @("both", "overseas")) { Install-OverseasPubKey }
if ($Target -in @("both", "domestic")) { Install-DomesticPubKey }

Write-Host "`n验证免密..." -ForegroundColor Cyan
& (Join-Path $PSScriptRoot "ssh_test_servers.ps1")
