# Domestic runtime watchdog: relaunch dead processes + alert on stale data (with cooldown).
# data_manager 存活判定：优先读 runtime/logs/data_manager_heartbeat.txt（不依赖进程枚举，兼容 SYSTEM 计划任务）。
# Run via Scheduled Task every 1 minute (Administrator recommended):
#   powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\Administrator\quant_futures\scripts\watchdog_domestic.ps1
$ErrorActionPreference = "Continue"
$root = "C:\Users\Administrator\quant_futures"
$py = "C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"
Set-Location $root

. (Join-Path $PSScriptRoot "load_feishu_webhook.ps1")
. (Join-Path $PSScriptRoot "resolve_domestic_paper.ps1")
$hook = Get-FeishuWebhook -Root $root

$stateDir = Join-Path $root "runtime\watchdog"
$watchdogLog = Join-Path $root "runtime\logs\watchdog.log"
$heartbeatFile = Join-Path $root "runtime\logs\data_manager_heartbeat.txt"
$HeartbeatMaxAgeSec = 420   # data_manager poll loop = 300s; keep margin for slow Tq rounds
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $root "runtime\logs") | Out-Null

$AlertCooldownSec = 1800
$DataStaleLimitSec = 1500
$DataStaleRestartCooldownSec = 1800
$RadarStaleLimitSec = 2400
$CsvSanityIntervalSec = 600
$FillSupervisionIntervalSec = 1800

function Test-FillSupervisionDue {
    $stamp = Join-Path $stateDir "fill_supervision.last"
    if (-not (Test-Path $stamp)) { return $true }
    return (((Get-Date) - (Get-Item $stamp).LastWriteTime).TotalSeconds -ge $FillSupervisionIntervalSec)
}

function Set-FillSupervisionStamp {
    Set-Content -Path (Join-Path $stateDir "fill_supervision.last") -Value (Now-Text)
}

function Get-FillSupervisionAlertDetails {
    $latest = Join-Path $root "runtime\logs\fill_supervision\fill_supervision_domestic_latest.json"
    if (-not (Test-Path $latest)) {
        return [pscustomobject]@{ fingerprint = "report-missing"; message = "latest fill supervision report missing" }
    }
    try {
        $payload = Get-Content -LiteralPath $latest -Raw -Encoding UTF8 | ConvertFrom-Json
        $rows = @($payload.invalid_new_fills)
        $ids = @($rows | ForEach-Object { [string]$_.order_id } | Where-Object { $_ } | Sort-Object -Unique)
        $fingerprint = if ($ids.Count -gt 0) { $ids -join "|" } else { "invalid-new-without-order-id" }
        $samples = @(
            $rows |
                Select-Object -First 3 |
                ForEach-Object {
                    $issues = @($_.issues) -join "; "
                    "{0} {1} {2}: {3}" -f $_.symbol, $_.strategy_id, $_.order_id, $issues
                }
        )
        $message = "Post-fill audit found {0} NEW unacknowledged INVALID fill(s) in last 72h." -f $rows.Count
        if ($samples.Count -gt 0) {
            $message += "`n" + ($samples -join "`n")
        }
        $message += "`nSee runtime/logs/fill_supervision/; acknowledge only after review."
        return [pscustomobject]@{ fingerprint = $fingerprint; message = $message }
    } catch {
        return [pscustomobject]@{ fingerprint = "report-parse-error"; message = "fill supervision report parse failed" }
    }
}

function Send-FillSupervisionAlertOnChange {
    $details = Get-FillSupervisionAlertDetails
    $fingerprintPath = Join-Path $stateDir "fill_supervision_invalid.fingerprint"
    $previous = ""
    if (Test-Path $fingerprintPath) {
        $previous = [string](Get-Content -LiteralPath $fingerprintPath -ErrorAction SilentlyContinue | Select-Object -First 1)
    }
    if ($previous -eq $details.fingerprint) {
        Log-Wd "fill_supervision invalid set unchanged; Feishu repeat suppressed"
        return
    }
    Set-Content -LiteralPath $fingerprintPath -Value $details.fingerprint -Encoding UTF8
    Remove-Item (Join-Path $stateDir "fill_supervision_invalid.alert") -ErrorAction SilentlyContinue
    Send-Feishu "fill_supervision_invalid" $details.message
}

function Invoke-FillSupervision {
    $auditScript = Join-Path $root "scripts\audit_paper_fills.py"
    if (-not (Test-Path $auditScript)) { return }
    $events = Join-Path $root "runtime\fengji_pending_orders\events.jsonl"
    if (-not (Test-Path $events)) { return }
    Log-Wd "fill_supervision start"
    $ackFile = Join-Path $root "runtime\fill_supervision_acknowledged.json"
    & $py $auditScript --root $root --profile domestic --since-hours 72 --fail-on-invalid --ack-file $ackFile --quiet
    $code = $LASTEXITCODE
    Set-FillSupervisionStamp
    if ($code -eq 2) {
        Send-FillSupervisionAlertOnChange
    } elseif ($code -ne 0) {
        Log-Wd "fill_supervision exit=$code (needs-data or partial)"
    } else {
        Remove-Item (Join-Path $stateDir "fill_supervision_invalid.fingerprint") -ErrorAction SilentlyContinue
        Clear-Alert "fill_supervision_invalid"
        Log-Wd "fill_supervision ok"
    }
}

function Now-Text { (Get-Date).ToString("yyyy-MM-dd HH:mm:ss") }

function Log-Wd {
    param([string]$Message)
    $line = "[$(Now-Text)] $Message"
    Add-Content -Path $watchdogLog -Value $line -Encoding UTF8
    Write-Output $line
}

function Send-Feishu {
    param([string]$Key, [string]$Message)
    $stamp = Join-Path $stateDir "$Key.alert"
    $now = [int][double]::Parse((Get-Date -UFormat %s))
    $last = 0
    if (Test-Path $stamp) { $last = [int](Get-Content $stamp -ErrorAction SilentlyContinue | Select-Object -First 1) }
    if (($now - $last) -lt $AlertCooldownSec) { return }
    Set-Content -Path $stamp -Value $now
    Log-Wd "ALERT[$Key] $Message"
    if ($hook) {
        $text = "WATCHDOG (domestic)`nTime: $(Now-Text)`n$Message"
        $payload = @{ msg_type = "text"; content = @{ text = $text } } | ConvertTo-Json -Compress
        try {
            $bytes = [Text.Encoding]::UTF8.GetBytes($payload)
            Invoke-RestMethod -Uri $hook -Method Post -ContentType "application/json; charset=utf-8" -Body $bytes -TimeoutSec 8 | Out-Null
        } catch {}
    }
}

function Clear-Alert { param([string]$Key) Remove-Item (Join-Path $stateDir "$Key.alert") -ErrorAction SilentlyContinue }

function Test-ProcAlive { param([string]$Pattern) [bool](Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match $Pattern -and $_.Name -match "python" }) }

function New-DetachedProcess { param([string]$Cmd) Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $Cmd; CurrentDirectory = $root } | Out-Null }

function Ensure-Proc {
    param([string]$Pattern, [string]$Name, [string]$Cmd)
    if (Test-ProcAlive $Pattern) { Clear-Alert "proc_$Name"; return }
    Log-Wd "$Name down, relaunching..."
    New-DetachedProcess $Cmd
    Start-Sleep -Seconds 6
    if (Test-ProcAlive $Pattern) {
        Clear-Alert "proc_$Name"
    } else {
        Send-Feishu "proc_$Name" "Process [$Name] down and relaunch FAILED, manual check needed"
    }
}

function Test-CsvSanityDue {
    $stamp = Join-Path $stateDir "csv_sanity.last"
    if (-not (Test-Path $stamp)) { return $true }
    return (((Get-Date) - (Get-Item $stamp).LastWriteTime).TotalSeconds -ge $CsvSanityIntervalSec)
}

function Set-CsvSanityStamp {
    Set-Content -Path (Join-Path $stateDir "csv_sanity.last") -Value (Now-Text)
}

function Invoke-CsvSanityCheck {
    $script = Join-Path $root "scripts\sanitize_domestic_futures_csv.py"
    if (-not (Test-Path $script)) { return }
    if (-not (Test-CsvSanityDue)) { return }
    Set-CsvSanityStamp

    $log = Join-Path $root "runtime\logs\futures_csv_sanity.log"
    $oldPythonPath = $env:PYTHONPATH
    try {
        $env:PYTHONPATH = "packages/fengji_core"
        $output = & $py $script --data-dir data 2>&1
        $exitCode = $LASTEXITCODE
    } finally {
        $env:PYTHONPATH = $oldPythonPath
    }

    $text = ($output | Out-String).Trim()
    if ($text) {
        Add-Content -Path $log -Encoding UTF8 -Value "[$(Now-Text)] dry-run"
        Add-Content -Path $log -Encoding UTF8 -Value $text
    }
    if ($exitCode -ne 0) {
        Send-Feishu "csv_sanity_error" "CSV sanity dry-run failed, check runtime/logs/futures_csv_sanity.log"
        return
    }

    $summary = $output | Select-String -Pattern "files_changed=(\d+)\s+rows_dropped=(\d+)\s+apply=False" | Select-Object -Last 1
    if (-not $summary) {
        Send-Feishu "csv_sanity_parse" "CSV sanity dry-run summary missing, check runtime/logs/futures_csv_sanity.log"
        return
    }
    $filesChanged = [int]$summary.Matches[0].Groups[1].Value
    $rowsDropped = [int]$summary.Matches[0].Groups[2].Value
    if ($filesChanged -gt 0 -or $rowsDropped -gt 0) {
        $sample = ($output | Where-Object { $_ -match "WOULD_CLEAN|SKIP" } | Select-Object -First 6) -join "`n"
        Send-Feishu "csv_sanity_bad_rows" ("Domestic futures CSV corrupt rows detected: files={0}, rows={1}.`n{2}`nAction: backup, clean one symbol, refetch from Tianqin, then audit simulated state." -f $filesChanged, $rowsDropped, $sample)
    } else {
        Clear-Alert "csv_sanity_bad_rows"
        Clear-Alert "csv_sanity_error"
        Clear-Alert "csv_sanity_parse"
    }
}

function Invoke-LogRotation {
    # 日志增长防护：runtime/logs 下 *.log 超过阈值(100MB) 时保留末尾 8MB，防止长期运行无限增长
    $rotatePy = Join-Path $root "scripts\rotate_log_tail.py"
    if (-not (Test-Path $rotatePy)) { return }
    $logsDir = Join-Path $root "runtime\logs"
    $paths = @(Get-ChildItem -Path $logsDir -Filter *.log -File -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)
    if ($paths.Count -eq 0) { return }
    $maxBytes = 100 * 1024 * 1024
    $keepBytes = 8 * 1024 * 1024
    & $py $rotatePy --max-bytes $maxBytes --keep-bytes $keepBytes @paths
    # 事件流水 events.jsonl 只追加不轮转会无限膨胀：曾涨到 11GB，导致 Windows 追加
    # 打开报 OSError [Errno 22]，挂单监控整轮回滚（成交/平仓/跳过全部写不进去）。
    # 单独用更大阈值/保留量（512MB/64MB），原地截断保持 inode，writer 无感知。
    $eventsFile = Join-Path $root "runtime\fengji_pending_orders\events.jsonl"
    if (Test-Path -LiteralPath $eventsFile) {
        & $py $rotatePy --max-bytes (512 * 1024 * 1024) --keep-bytes (64 * 1024 * 1024) $eventsFile
    }
}

$hookSet = if ($hook) { "set FENGJI_FEISHU_WEBHOOK=$hook&& " } else { "" }
$prefix = "cmd.exe /d /c cd /d `"$root`" && set `"PYTHONPATH=src;packages/fengji_core`"&& set FENGJI_MARKET=futures&& set PYTHONIOENCODING=utf-8&& set PYTHONUTF8=1&& $hookSet"
$symbols = "SA,FG,RB,PG,FU,CJ,OI,SP,LH,JD,SI,PP,SH,EB,NI,SR,EG,AO,JM,EC,RU,BR,SF,M,MA,P,V,TA,UR,CF,LC,AU,AG,SC"
$stateFile = "runtime\fengji_pending_orders\futures_pending_state.json"
$paper = Get-DomesticPaperScript -Root $root

$cmdData = $prefix + "`"$py`" -u data_manager_futures.py >> runtime\logs\data_manager_futures.log 2>> runtime\logs\data_manager_futures_err.log"
$cmdPaper = $prefix + "`"$py`" -u `"$paper`" >> `"runtime\logs\paper_futures_run.log`" 2>> `"runtime\logs\paper_futures_err.log`""
$cmdRadar = $prefix + "`"$py`" -u `"src\fengji_radar_order_loop.py`" --market futures --data-dir data --symbols `"$symbols`" --radar-dir runtime\fengji_radar --pending-dir runtime\fengji_pending_orders --monitor-state `"$stateFile`" --include-triggered --loop-seconds 600 --daily-tail 1095 --h1-tail 2400 --m15-tail 960 --top-n 40 >> `"runtime\logs\futures_radar_order_loop.log`" 2>> `"runtime\logs\futures_radar_order_loop_err.log`""
$cmdPending = $prefix + "`"$py`" -u `"src\fengji_futures_pending_order_monitor.py`" --orders-file runtime\fengji_pending_orders\pending_orders.json --out-dir runtime\fengji_pending_orders --state-file runtime\fengji_pending_orders\futures_pending_state.json --paper-state-file runtime\fengji_futures\state_futures_v2.json --trade-csv runtime\fengji_futures\trades_futures_astock.csv --data-dir data --os-state-dir runtime\fengji_os_state --price-timeframes 15m,1h,1d --loop-seconds 5 --max-ds01-entries 3 --max-open-positions-per-symbol 3 --lots 1 --enforce-valid-until >> `"runtime\logs\futures_pending_order_monitor.log`" 2>> `"runtime\logs\futures_pending_order_monitor_err.log`""

function Get-DataManagerHeartbeatAge {
    if (-not (Test-Path $heartbeatFile)) { return $null }
    return ((Get-Date) - (Get-Item $heartbeatFile).LastWriteTime).TotalSeconds
}

function Get-Latest15mDataAge {
    $csv = Get-ChildItem (Join-Path $root "data\15m") -Filter "*.csv" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $csv) { return $null }
    return ((Get-Date) - $csv.LastWriteTime).TotalSeconds
}

function Get-DataManagerHeartbeatNote {
    if (-not (Test-Path $heartbeatFile)) { return "" }
    $line = Get-Content $heartbeatFile -TotalCount 1 -ErrorAction SilentlyContinue
    if ($line -match "pid=\d+\s+(.+)$") { return $Matches[1].Trim() }
    return ""
}

function Get-DataManagerProcs {
    @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -match "python" -and $_.CommandLine -and ($_.CommandLine -match "data_manager_futures\.py")
    })
}

function Test-DataManagerAlive {
    $dataAge = Get-Latest15mDataAge
    $note = Get-DataManagerHeartbeatNote
    # connect_retry 心跳不能掩盖 CSV 停更：否则 watchdog 认为进程健康但不写盘
    if ($null -ne $dataAge -and $dataAge -gt $DataStaleLimitSec -and $note -match "connect_retry|connect") {
        return $false
    }
    $hbAge = Get-DataManagerHeartbeatAge
    if ($null -ne $hbAge -and $hbAge -lt $HeartbeatMaxAgeSec) { return $true }
    if ($null -ne $dataAge -and $dataAge -lt $DataStaleLimitSec) { return $true }
    if ((Get-DataManagerProcs).Count -ge 1) { return $false }
    return $false
}

function Wait-DataManagerUp {
    param([int]$TimeoutSec = 30)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-DataManagerAlive) { return $true }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Test-DataManagerLaunchLock {
    $lock = Join-Path $stateDir "data_manager_start.lock"
    if (-not (Test-Path $lock)) { return $false }
    return (((Get-Date) - (Get-Item $lock).LastWriteTime).TotalSeconds -lt 30)
}

function Set-DataManagerLaunchLock { Set-Content -Path (Join-Path $stateDir "data_manager_start.lock") -Value (Now-Text) }
function Clear-DataManagerLaunchLock { Remove-Item (Join-Path $stateDir "data_manager_start.lock") -ErrorAction SilentlyContinue }

function Test-DataStaleRestartDue {
    $stamp = Join-Path $stateDir "data_stale_restart.last"
    if (-not (Test-Path $stamp)) { return $true }
    return (((Get-Date) - (Get-Item $stamp).LastWriteTime).TotalSeconds -ge $DataStaleRestartCooldownSec)
}

function Set-DataStaleRestartStamp {
    Set-Content -Path (Join-Path $stateDir "data_stale_restart.last") -Value (Now-Text)
}

function Ensure-SingleDataManager {
    $procs = Get-DataManagerProcs
    if ($procs.Count -le 1) { return $procs.Count }
    Log-Wd "data_manager duplicate python count=$($procs.Count), stopping extras..."
    foreach ($p in $procs) {
        try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop } catch {}
    }
    Start-Sleep -Seconds 2
    return 0
}

function Ensure-DataManager {
    if (Test-DataManagerLaunchLock) { return }
    if (Test-DataManagerAlive) {
        Clear-Alert "proc_data_manager"
        if ((Get-DataManagerProcs).Count -gt 1) { Ensure-SingleDataManager | Out-Null }
        return
    }
    Log-Wd "data_manager down (no heartbeat), relaunching..."
    Set-DataManagerLaunchLock
    try {
        New-DetachedProcess $cmdData
        if (Wait-DataManagerUp -TimeoutSec 30) {
            Clear-Alert "proc_data_manager"
            if ((Get-DataManagerProcs).Count -gt 1) { Ensure-SingleDataManager | Out-Null }
        } else {
            Send-Feishu "proc_data_manager" "Process [data_manager] down and relaunch FAILED, manual check needed"
        }
    } finally {
        Clear-DataManagerLaunchLock
    }
}

function Restart-DataManagerForStaleData {
    param([double]$AgeSec)
    if (-not (Test-DataStaleRestartDue)) { return }
    Log-Wd ("data_manager stale-data restart: 15m age={0} min, stopping current process and relaunching..." -f [int]($AgeSec / 60))
    Set-DataStaleRestartStamp
    foreach ($p in Get-DataManagerProcs) {
        try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop } catch {}
    }
    Start-Sleep -Seconds 3
    New-DetachedProcess $cmdData
    if (Wait-DataManagerUp -TimeoutSec 45) {
        Clear-Alert "proc_data_manager"
        Log-Wd "data_manager stale-data restart launched"
    } else {
        Send-Feishu "proc_data_manager" "Process [data_manager] stale-data restart FAILED, manual check needed"
    }
}

Ensure-DataManager
Ensure-Proc "01-08" "paper_monitor" $cmdPaper
Ensure-Proc "fengji_radar_order_loop\.py" "radar_loop" $cmdRadar
Ensure-Proc "fengji_futures_pending_order_monitor\.py" "pending_monitor" $cmdPending

function In-TradingWindow {
    $n = Get-Date
    $dow = [int]$n.DayOfWeek
    $t = $n.TimeOfDay
    function Between($a, $b) { ($t -ge [TimeSpan]$a) -and ($t -le [TimeSpan]$b) }
    if ($dow -ge 1 -and $dow -le 5) {
        if (Between "09:00:00" "11:30:00") { return $true }
        if (Between "13:00:00" "15:15:00") { return $true }
        if (Between "21:00:00" "23:59:59") { return $true }
    }
    if ($dow -ge 2 -and $dow -le 6) {
        if (Between "00:00:00" "02:35:00") { return $true }
    }
    return $false
}

$now = Get-Date
if (In-TradingWindow) {
    $csv = Get-ChildItem (Join-Path $root "data\15m") -Filter "*.csv" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($csv) {
        $age = ($now - $csv.LastWriteTime).TotalSeconds
        if ($age -gt $DataStaleLimitSec) {
            $hbNote = Get-DataManagerHeartbeatNote
            $detail = "15m data stale for {0} min (limit {1} min) during trading window, data pump suspect" -f [int]($age/60), [int]($DataStaleLimitSec/60)
            if ($hbNote -match "connect_retry|connect") {
                $detail += "; Tianqin connect failing (heartbeat=$hbNote), check TQ_PHONE/TQ_PASS subscription"
            }
            Send-Feishu "data_stale" $detail
            Restart-DataManagerForStaleData -AgeSec $age
        } else { Clear-Alert "data_stale" }
    }
    $radar = Join-Path $root "runtime\fengji_radar\radar.json"
    if (Test-Path $radar) {
        $age = ($now - (Get-Item $radar).LastWriteTime).TotalSeconds
        if ($age -gt $RadarStaleLimitSec) {
            Send-Feishu "radar_stale" ("radar.json stale for {0} min (limit {1} min), radar suspect" -f [int]($age/60), [int]($RadarStaleLimitSec/60))
        } else { Clear-Alert "radar_stale" }
    }
} else {
    Clear-Alert "data_stale"; Clear-Alert "radar_stale"
}

Invoke-CsvSanityCheck

if (Test-FillSupervisionDue) { Invoke-FillSupervision }

Invoke-LogRotation

Log-Wd "watchdog ok"
