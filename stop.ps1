$ErrorActionPreference = "Continue"

Write-Host "`n========== Stopping Services ==========`n" -ForegroundColor Cyan

Write-Host "[INFO] Stopping Discord bot..." -ForegroundColor Blue; docker compose stop discord-bot 2>$null; Start-Sleep 2
Write-Host "[INFO] Stopping News Server..." -ForegroundColor Blue; docker compose stop news-server 2>$null; Start-Sleep 2
Write-Host "[INFO] Stopping PostgreSQL..." -ForegroundColor Blue; docker compose stop postgres 2>$null

Write-Host ""; Write-Host "[OK] All services stopped!" -ForegroundColor Green; Write-Host ""
docker compose ps
