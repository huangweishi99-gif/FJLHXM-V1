# 为本机生成峰极专用 SSH 密钥，并打印公钥（需一次性写入服务器 authorized_keys）
param(
    [ValidateSet("domestic", "overseas", "both")]
    [string]$Target = "both",
    [string]$SshDir = "$env:USERPROFILE\.ssh"
)

$ErrorActionPreference = "Stop"

function Ensure-KeyPair {
    param([string]$Name)
    $priv = Join-Path $SshDir $Name
    $pub = "$priv.pub"
    if (-not (Test-Path $SshDir)) {
        New-Item -ItemType Directory -Path $SshDir -Force | Out-Null
    }
    if (-not (Test-Path $priv)) {
        Write-Host "Generating $Name ..." -ForegroundColor Yellow
        ssh-keygen -t ed25519 -f $priv -N '""' -C "fengji-$Name"
    } else {
        Write-Host "Key exists: $priv" -ForegroundColor DarkGray
    }
    if (-not (Test-Path $pub)) {
        throw "Public key missing: $pub"
    }
    return $pub
}

$map = @{
    domestic = @{ Key = "quant_domestic_ed25519"; Host = "domestic-quant"; User = "Administrator"; Note = "Windows: 公钥写入 C:\Users\Administrator\.ssh\authorized_keys 或 C:\ProgramData\ssh\administrators_authorized_keys（需 ACL 正确）" }
    overseas = @{ Key = "quant_overseas_ed25519"; Host = "overseas-quant"; User = "ubuntu"; Note = "Linux: ssh USER@HOST 'mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys'" }
}

$targets = if ($Target -eq "both") { @("domestic", "overseas") } else { @($Target) }

Write-Host "SSH dir: $SshDir" -ForegroundColor Cyan
Write-Host "After installing public keys, merge scripts/ssh_config.example into $SshDir\config`n"

foreach ($t in $targets) {
    $info = $map[$t]
    $pubPath = Ensure-KeyPair -Name $info.Key
    $pub = (Get-Content $pubPath -Raw).Trim()
    Write-Host "========== $t ($($info.Host)) ==========" -ForegroundColor Green
    Write-Host $pub
    Write-Host $info.Note -ForegroundColor DarkYellow
    Write-Host "One-time install (will prompt password once):" -ForegroundColor Cyan
    if ($t -eq "overseas") {
        Write-Host "  Get-Content `"$pubPath`" | ssh $($info.User)@$($info.Host) `"mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys`""
    } else {
        Write-Host "  type `"$pubPath`" | ssh $($info.User)@$($info.Host) `"powershell -NoProfile -Command `"`$d='C:\Users\Administrator\.ssh'; New-Item -ItemType Directory -Force -Path `$d | Out-Null; Get-Content - | Add-Content -Path (Join-Path `$d 'authorized_keys')`"`""
    }
    Write-Host ""
}

Write-Host "Verify:" -ForegroundColor Cyan
Write-Host "  .\scripts\ssh_test_servers.ps1"
