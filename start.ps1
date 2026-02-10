$ErrorActionPreference = "Continue"

function Write-Status { param($msg) Write-Host "[INFO] $msg" -ForegroundColor Blue }
function Write-OK { param($msg) Write-Host "[OK] $msg" -ForegroundColor Green }

function Wait-ForHealthy {
    param([string]$Container, [int]$MaxAttempts = 30)
    Write-Status "Waiting for $Container..."
    for ($i = 1; $i -le $MaxAttempts; $i++) {
        try {
            $status = docker inspect --format='{{.State.Health.Status}}' $Container 2>$null
            if ($status -eq "healthy") { Write-OK "$Container is healthy"; return $true }
        } catch {}
        Write-Host "." -NoNewline
        Start-Sleep -Seconds 2
    }
    Write-Host ""; Write-Status "$Container did not become healthy in time, continuing..."
    return $true
}

function Wait-ForRunning {
    param([string]$Container, [int]$MaxAttempts = 15)
    Write-Status "Waiting for $Container..."
    for ($i = 1; $i -le $MaxAttempts; $i++) {
        try {
            $status = docker inspect --format='{{.State.Status}}' $Container 2>$null
            if ($status -eq "running") { Write-OK "$Container is running"; return $true }
        } catch {}
        Write-Host "." -NoNewline
        Start-Sleep -Seconds 1
    }
    Write-Host ""; Write-Host "[ERROR] $Container failed to start" -ForegroundColor Red
    return $false
}

Write-Host "`n========== Starting Services ==========`n" -ForegroundColor Cyan

Write-Status "PHASE 1: Database"
docker compose up -d postgres; Wait-ForHealthy "forex-postgres" 60; Start-Sleep 3
Write-OK "Database OK`n"

Write-Status "PHASE 2: News Server"
docker compose up -d news-server; Wait-ForRunning "news-server" 30; Start-Sleep 3
Write-OK "News Server OK`n"

Write-Status "PHASE 3: Discord Bot"
docker compose up -d discord-bot; Wait-ForRunning "bot-discord" 30; Start-Sleep 3
Write-OK "Bot OK`n"

Write-Host "========== All Services Started ==========" -ForegroundColor Green
docker compose ps
Write-Host "`nNews Server: http://localhost:8000/health"
