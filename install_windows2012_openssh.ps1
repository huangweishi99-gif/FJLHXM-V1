# Install Win32-OpenSSH on Windows Server 2012 R2.
# Run this script in an elevated PowerShell window on the remote Windows server.

$ErrorActionPreference = "Stop"

function Assert-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Please run PowerShell as Administrator."
    }
}

function Add-ToSystemPath {
    param([string]$PathToAdd)
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $parts = $machinePath -split ";" | Where-Object { $_ -ne "" }
    if ($parts -notcontains $PathToAdd) {
        [Environment]::SetEnvironmentVariable("Path", ($machinePath.TrimEnd(";") + ";" + $PathToAdd), "Machine")
    }
}

Assert-Admin

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$zip = Join-Path $env:TEMP "OpenSSH-Win64.zip"
$tmp = Join-Path $env:TEMP "OpenSSH-Win64"
$dest = "C:\Program Files\OpenSSH"
$backup = "C:\Program Files\OpenSSH_backup_$stamp"
$downloadUrl = "https://github.com/PowerShell/Win32-OpenSSH/releases/latest/download/OpenSSH-Win64.zip"

Write-Host "Installing Win32-OpenSSH for Windows Server 2012 R2..."
Write-Host "Download URL: $downloadUrl"

if (Test-Path $tmp) {
    Remove-Item -LiteralPath $tmp -Recurse -Force
}

if (Test-Path $zip) {
    Remove-Item -LiteralPath $zip -Force
}

if (Test-Path $dest) {
    Write-Host "Existing OpenSSH folder found. Backing up to: $backup"
    Move-Item -LiteralPath $dest -Destination $backup
}

Write-Host "Downloading OpenSSH..."
Invoke-WebRequest -Uri $downloadUrl -OutFile $zip -UseBasicParsing

Write-Host "Extracting..."
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::ExtractToDirectory($zip, $tmp)

New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item -Path (Join-Path $tmp "OpenSSH-Win64\*") -Destination $dest -Recurse -Force

Set-Location $dest

Write-Host "Installing sshd service..."
powershell.exe -ExecutionPolicy Bypass -File .\install-sshd.ps1

Add-ToSystemPath -PathToAdd $dest

Write-Host "Configuring firewall..."
netsh advfirewall firewall delete rule name="OpenSSH Server sshd" | Out-Null 2>$null
netsh advfirewall firewall add rule name="OpenSSH Server sshd" dir=in action=allow protocol=TCP localport=22 | Out-Null

Write-Host "Starting sshd..."
Set-Service sshd -StartupType Automatic
Start-Service sshd

Write-Host ""
Write-Host "===== sshd service ====="
Get-Service sshd

Write-Host ""
Write-Host "===== port 22 listener ====="
netstat -ano | findstr ":22"

Write-Host ""
Write-Host "OpenSSH install completed. Test from your local PC:"
Write-Host "ssh Administrator@106.53.107.248"
