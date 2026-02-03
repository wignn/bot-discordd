$ErrorActionPreference = "Continue"

function Write-Status { param($msg) Write-Host "[INFO] $msg" -ForegroundColor Blue }
function Write-OK { param($msg) Write-Host "[OK] $msg" -ForegroundColor Green }

Write-Host "`n========== Stopping Services ==========`n" -ForegroundColor Cyan

Write-Status "Stopping Discord bot..."; docker compose stop discord-bot 2>$null; Start-Sleep 2
Write-Status "Stopping Lavalink..."; docker compose stop lavalink 2>$null; Start-Sleep 2
Write-Status "Stopping Flower..."; docker compose stop flower 2>$null
Write-Status "Stopping Celery beat..."; docker compose stop news-beat 2>$null
Write-Status "Stopping Celery worker..."; docker compose stop news-worker 2>$null; Start-Sleep 2
Write-Status "Stopping News API..."; docker compose stop news-api 2>$null; Start-Sleep 2
Write-Status "Stopping RabbitMQ..."; docker compose stop rabbitmq 2>$null
Write-Status "Stopping Redis..."; docker compose stop redis 2>$null
Write-Status "Stopping PostgreSQL..."; docker compose stop postgres 2>$null

Write-Host ""; Write-OK "All services stopped!"; Write-Host ""
docker compose ps
