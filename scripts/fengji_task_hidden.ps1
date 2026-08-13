$ErrorActionPreference = "Stop"

function New-FengJiHiddenVbsLauncher {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string]$Command
    )

    $launcherDir = Join-Path $env:LOCALAPPDATA "FengJi"
    New-Item -ItemType Directory -Force -Path $launcherDir | Out-Null

    $safeName = ($Name -replace "[^A-Za-z0-9_.-]", "_")
    $launcher = Join-Path $launcherDir "$safeName.vbs"
    $escapedCommand = $Command.Replace('"', '""')
    $content = @"
Option Explicit

Dim shell
Dim command
Dim exitCode

Set shell = CreateObject("WScript.Shell")
command = "$escapedCommand"
exitCode = shell.Run(command, 0, True)
WScript.Quit exitCode
"@
    Set-Content -LiteralPath $launcher -Value $content -Encoding ASCII
    return $launcher
}

function New-FengJiHiddenTaskAction {
    param(
        [Parameter(Mandatory = $true)]
        [string]$LauncherPath
    )

    return New-ScheduledTaskAction `
        -Execute "wscript.exe" `
        -Argument "//B //Nologo `"$LauncherPath`""
}
