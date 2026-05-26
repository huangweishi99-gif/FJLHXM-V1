# Repair SSH public-key login for Administrator on the domestic Windows server.
# Run this script in an elevated PowerShell window on the remote Windows server.

$ErrorActionPreference = "Stop"

$key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEZ2YgDll5k+YNYCpdqk6iK4+hreoy8tXmtsJdsfaZVp codex-domestic-quant-futures"
$adminAuth = "C:\ProgramData\ssh\administrators_authorized_keys"
$userDir = "C:\Users\Administrator\.ssh"
$userAuth = "C:\Users\Administrator\.ssh\authorized_keys"
$config = "C:\ProgramData\ssh\sshd_config"

New-Item -ItemType Directory -Force -Path "C:\ProgramData\ssh" | Out-Null
New-Item -ItemType Directory -Force -Path $userDir | Out-Null

foreach ($auth in @($adminAuth, $userAuth)) {
    if (-not (Test-Path $auth)) {
        New-Item -ItemType File -Force -Path $auth | Out-Null
    }
    $content = Get-Content $auth -Raw -ErrorAction SilentlyContinue
    if ($content -notlike ("*" + $key + "*")) {
        Add-Content -Path $auth -Value $key
    }
}

icacls $adminAuth /inheritance:r
icacls $adminAuth /grant:r "Administrators:F" "SYSTEM:F"
icacls $adminAuth /remove:g "Users" "Authenticated Users" "Everyone"

icacls $userDir /inheritance:r
icacls $userDir /grant:r "Administrator:F" "Administrators:F" "SYSTEM:F"

icacls $userAuth /inheritance:r
icacls $userAuth /grant:r "Administrator:F" "Administrators:F" "SYSTEM:F"

if (Test-Path $config) {
    Copy-Item $config ($config + ".bak_" + (Get-Date -Format "yyyyMMdd_HHmmss")) -Force
    $text = Get-Content $config -Raw
    $text = $text -replace "(?im)^\s*PubkeyAuthentication\s+.*$", "PubkeyAuthentication yes"
    if ($text -notmatch "(?im)^\s*PubkeyAuthentication\s+") {
        $text += "`r`nPubkeyAuthentication yes`r`n"
    }
    Set-Content -Path $config -Value $text -Encoding ascii
}

Restart-Service sshd

Write-Host "authorized_keys repair OK"
Write-Host "===== sshd ====="
Get-Service sshd
Write-Host "===== key files ====="
Get-Item $adminAuth, $userAuth | Select-Object FullName, Length, LastWriteTime
Write-Host "===== sshd_config key lines ====="
Get-Content $config | Select-String -Pattern "PubkeyAuthentication|AuthorizedKeysFile|Match Group" -Context 0,1
