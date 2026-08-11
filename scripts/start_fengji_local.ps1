# 峰极量化 · 本地一键启动（无需手动配置服务器）
# 自动：Docker PG → migration 007 → 生成本地密钥 → 启动 API
param(
    [int]$Port = 8000,
    [switch]$SkipDocker,
    [switch]$SetupOnly
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

$secretsDir = Join-Path $root "runtime\secrets"
$localEnv = Join-Path $secretsDir "fengji_local.env"
New-Item -ItemType Directory -Force -Path $secretsDir | Out-Null

function New-RandomToken([int]$ByteCount = 32) {
    $bytes = New-Object byte[] $ByteCount
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return [Convert]::ToBase64String($bytes).TrimEnd("=")
}

if (-not (Test-Path -LiteralPath $localEnv)) {
    Write-Host "[setup] 生成本地私密配置: runtime/secrets/fengji_local.env" -ForegroundColor Cyan
    $jwt = New-RandomToken 48
    $admin = New-RandomToken 24
    @(
        "# FengJi local dev — auto generated, DO NOT commit",
        "DATABASE_URL=postgresql+psycopg://fengji:fengji_dev@localhost:5432/fengji",
        "FENGJI_JWT_SECRET=$jwt",
        "FENGJI_ADMIN_TOKEN=$admin",
        "FENGJI_ALLOW_MANUAL_SUBSCRIPTION_CONFIRM=1",
        "FENGJI_SUBSCRIPTION_PERIOD_DAYS=30"
    ) | Set-Content -LiteralPath $localEnv -Encoding UTF8
} else {
    Write-Host "[setup] 使用已有 runtime/secrets/fengji_local.env" -ForegroundColor DarkGray
}

Get-Content -LiteralPath $localEnv -Encoding UTF8 | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) { return }
    if ($line -match "^([^=]+)=(.*)$") {
        Set-Item -Path ("env:" + $matches[1].Trim()) -Value $matches[2].Trim()
    }
}

if (-not $SkipDocker) {
    Write-Host "[docker] 启动 PostgreSQL (docker compose up -d) ..." -ForegroundColor Cyan
    docker compose up -d
    $deadline = (Get-Date).AddMinutes(2)
    $ready = $false
    while ((Get-Date) -lt $deadline) {
        try {
            docker compose exec -T db pg_isready -U fengji -d fengji 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        } catch { }
        Start-Sleep -Seconds 2
    }
    if (-not $ready) {
        throw "PostgreSQL 未在 2 分钟内就绪；请确认 Docker Desktop 已运行"
    }
    Write-Host "[docker] PostgreSQL 就绪" -ForegroundColor Green
}

$env:PYTHONPATH = "src;packages/fengji_core;services"
Write-Host "[db] alembic upgrade head ..." -ForegroundColor Cyan
python -m alembic upgrade head
python -m alembic current

if ($SetupOnly) {
    Write-Host "`n本地环境已就绪（未启动 API）。启动命令：" -ForegroundColor Green
    Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\run_fengji_api.ps1" -ForegroundColor Yellow
    exit 0
}

$adminToken = $env:FENGJI_ADMIN_TOKEN
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " 峰极量化 · 本地环境已就绪" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host " Web 首页:    http://127.0.0.1:$Port/web/index.html"
Write-Host " 登录/注册:   http://127.0.0.1:$Port/web/login.html"
Write-Host " 模拟监测:    http://127.0.0.1:$Port/web/monitor.html"
Write-Host " 管理后台:    http://127.0.0.1:$Port/web/admin.html"
Write-Host ""
Write-Host " 管理 Token（仅本地，保存在 fengji_local.env）:" -ForegroundColor Yellow
Write-Host "   $adminToken"
Write-Host ""
Write-Host " 在管理页粘贴上述 Token 即可查看运行概览。" -ForegroundColor DarkGray
Write-Host " 按 Ctrl+C 停止 API。" -ForegroundColor DarkGray
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

& (Join-Path $PSScriptRoot "run_fengji_api.ps1") -Port $Port
