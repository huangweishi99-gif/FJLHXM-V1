# Install Win32-OpenSSH v8.1 on Windows Server 2012 R2 from a local zip package.
# Run this script in an elevated PowerShell window on the remote Windows server.

$ErrorActionPreference = "Stop"
$log = "C:\Users\Administrator\Desktop\openssh_v81_install_log.txt"

Start-Transcript -Path $log -Append

try {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Please run PowerShell as Administrator."
    }

    $zip = "C:\Users\Administrator\Desktop\openssh_windows2012_v81_package\OpenSSH-Win64.zip"
    $tmp = "C:\Users\Administrator\Desktop\openssh_windows2012_v81_package\extract_tmp"
    $dest = "C:\Program Files\OpenSSH"
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $backup = "C:\Program Files\OpenSSH_backup_before_v81_$stamp"

    if (-not (Test-Path $zip)) {
        throw "Local OpenSSH zip not found: $zip"
    }
    if ((Get-Item $zip).Length -lt 1000000) {
        throw "OpenSSH-Win64.zip is too small; copy may be incomplete."
    }

    try {
        Stop-Service sshd -ErrorAction SilentlyContinue
        Stop-Service ssh-agent -ErrorAction SilentlyContinue
    } catch {}

    if (Test-Path "$dest\uninstall-sshd.ps1") {
        Set-Location $dest
        powershell.exe -ExecutionPolicy Bypass -File .\uninstall-sshd.ps1
        Set-Location "C:\Users\Administrator"
    }

    if (Test-Path $tmp) {
        Remove-Item -LiteralPath $tmp -Recurse -Force
    }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory($zip, $tmp)

    if (-not (Test-Path (Join-Path $tmp "OpenSSH-Win64\install-sshd.ps1"))) {
        throw "install-sshd.ps1 was not found after extracting the zip."
    }
    if (-not (Test-Path (Join-Path $tmp "OpenSSH-Win64\sshd.exe"))) {
        throw "sshd.exe was not found after extracting the zip."
    }

    if (Test-Path $dest) {
        Move-Item -LiteralPath $dest -Destination $backup -Force
    }

    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    Copy-Item -Path (Join-Path $tmp "OpenSSH-Win64\*") -Destination $dest -Recurse -Force

    Set-Location $dest
    powershell.exe -ExecutionPolicy Bypass -File .\install-sshd.ps1

    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    if (($machinePath -split ";") -notcontains $dest) {
        [Environment]::SetEnvironmentVariable("Path", ($machinePath.TrimEnd(";") + ";" + $dest), "Machine")
    }

    New-Item -Path "HKLM:\SOFTWARE\OpenSSH" -Force | Out-Null
    New-ItemProperty -Path "HKLM:\SOFTWARE\OpenSSH" -Name DefaultShell -Value "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -PropertyType String -Force | Out-Null

    netsh advfirewall firewall delete rule name="OpenSSH Server sshd" | Out-Null 2>$null
    netsh advfirewall firewall add rule name="OpenSSH Server sshd" dir=in action=allow protocol=TCP localport=22 | Out-Null

    Set-Service sshd -StartupType Automatic
    Start-Service sshd

    Write-Host "===== sshd version ====="
    & "$dest\sshd.exe" -V

    Write-Host "===== Service ====="
    Get-Service sshd

    Write-Host "===== Port 22 ====="
    netstat -ano | findstr ":22"

    Write-Host "OpenSSH v8.1 install completed. Test from local PC: ssh Administrator@106.53.107.248"
}
catch {
    Write-Host "===== ERROR =====" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host $_.ScriptStackTrace -ForegroundColor Yellow
}
finally {
    Stop-Transcript
    Write-Host ("Log: " + $log)
    Read-Host "Press Enter to close"
}
