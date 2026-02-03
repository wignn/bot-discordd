$ErrorActionPreference = "Continue"

function Write-Status { param($msg) Write-Host "[INFO] $msg" -ForegroundColor Blue }
function Write-OK { param($msg) Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err { param($msg) Write-Host "[ERROR] $msg" -ForegroundColor Red }

function Wait-ForHealthy {
    param([string]$Container, [int]$MaxAttempts = 30)
    Write-Status "Waiting for $Container to be healthy..."
    for ($i = 1; $i -le $MaxAttempts; $i++) {
        try {
            $status = docker inspect --format='{{.State.Health.Status}}' $Container 2>$null
            if ($status -eq "healthy") { Write-OK "$Container is healthy"; return $true }
        } catch {}
        Write-Host "." -NoNewline
        Start-Sleep -Seconds 2
    }
    Write-Host ""; Write-Warn "$Container did not become healthy in time, continuing..."
    return $true
}

function Wait-ForRunning {
    param([string]$Container, [int]$MaxAttempts = 15)
    Write-Status "Waiting for $Container to start..."
    for ($i = 1; $i -le $MaxAttempts; $i++) {
        try {
            $status = docker inspect --format='{{.State.Status}}' $Container 2>$null
            if ($status -eq "running") { Write-OK "$Container is running"; return $true }
        } catch {}
        Write-Host "." -NoNewline
        Start-Sleep -Seconds 1
    }
    Write-Host ""; Write-Err "$Container failed to start"
    return $false
}

Write-Host "`n========== Starting Services ==========`n" -ForegroundColor Cyan

Write-Status "PHASE 1: Infrastructure"
docker compose up -d postgres; Wait-ForHealthy "forex-postgres" 60; Start-Sleep 3
docker compose up -d redis; Wait-ForHealthy "forex-redis" 30; Start-Sleep 2
docker compose up -d rabbitmq; Wait-ForHealthy "forex-rabbitmq" 60; Start-Sleep 5
Write-OK "Infrastructure OK`n"

Write-Status "PHASE 2: Backend"
docker compose up -d news-api; Wait-ForRunning "news-api" 30; Start-Sleep 5
docker compose up -d news-worker; Wait-ForRunning "news-worker" 20; Start-Sleep 3
docker compose up -d news-beat; Wait-ForRunning "news-beat" 20; Start-Sleep 2
docker compose up -d flower; Wait-ForRunning "news-flower" 15; Start-Sleep 2
Write-OK "Backend OK`n"

Write-Status "PHASE 3: Bot"
docker compose up -d lavalink; Wait-ForRunning "lavalink" 30; Start-Sleep 10
docker compose up -d discord-bot; Wait-ForRunning "bot-discord" 30; Start-Sleep 3
Write-OK "Bot OK`n"

Write-Host "========== All Services Started ==========" -ForegroundColor Green
docker compose ps
Write-Host "`nNews API: http://localhost:8000/docs | Flower: http://localhost:5555 | RabbitMQ: http://localhost:15672"
