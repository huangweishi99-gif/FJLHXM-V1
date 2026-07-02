# Preflight before PostgreSQL install on low-spec domestic server (2c4G).
param(
    [string]$Root = "C:\Users\Administrator\quant_futures",
    [long]$MinFreeRamMb = 700,
    [long]$MinFreeDiskGb = 3,
    [int]$MaxCpuLoadPct = 85
)

$ErrorActionPreference = "Stop"
$os = Get-CimInstance Win32_OperatingSystem
$freeRamMb = [math]::Round($os.FreePhysicalMemory / 1024)
$totalRamMb = [math]::Round($os.TotalVisibleMemorySize / 1024)
$disk = Get-PSDrive -Name C
$freeDiskGb = [math]::Round($disk.Free / 1GB, 1)
$cpu = (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average

Write-Host "preflight: RAM free=${freeRamMb}MB / total=${totalRamMb}MB; disk C free=${freeDiskGb}GB; CPU avg=${cpu}%"

$issues = @()
if ($freeRamMb -lt $MinFreeRamMb) { $issues += "free RAM ${freeRamMb}MB < ${MinFreeRamMb}MB" }
if ($freeDiskGb -lt $MinFreeDiskGb) { $issues += "free disk ${freeDiskGb}GB < ${MinFreeDiskGb}GB" }
if ($cpu -gt $MaxCpuLoadPct) { $issues += "CPU load ${cpu}% > ${MaxCpuLoadPct}%" }

if ($issues.Count -gt 0) {
    Write-Host "PREFLIGHT_FAIL: $($issues -join '; ')" -ForegroundColor Red
    Write-Host "Wait for data_manager/radar idle or free memory before PG install." -ForegroundColor Yellow
    exit 1
}
Write-Host "PREFLIGHT_OK" -ForegroundColor Green
