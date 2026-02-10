param(
    [string]$Tag = "latest"
)

$ErrorActionPreference = "Stop"

$NEWS_SERVER = "wign/news-server"
$BOT_IMAGE = "wign/bot-discord"
$FRONTEND = "wign/forex-frontend"

Write-Host "================================" -ForegroundColor Cyan
Write-Host "Building and pushing Docker images"
Write-Host "Tag: $Tag"
Write-Host "================================" -ForegroundColor Cyan

Write-Host ""
Write-Host "[1/4] Setting up Docker buildx..." -ForegroundColor Yellow
docker buildx create --name multibuilder --driver docker-container --use 2>$null
docker buildx inspect --bootstrap

Write-Host ""
Write-Host "[2/4] Building and pushing News Server..." -ForegroundColor Yellow
docker buildx build `
    --platform linux/amd64 `
    -f infrastructure/docker/Dockerfile.server `
    -t "${NEWS_SERVER}:${Tag}" `
    --push `
    ./news-server

if ($LASTEXITCODE -ne 0) { throw "Failed to build News Server" }

Write-Host ""
Write-Host "[3/4] Building and pushing Discord Bot..." -ForegroundColor Yellow
docker buildx build `
    --platform linux/amd64 `
    -f infrastructure/docker/Dockerfile.bot `
    -t "${BOT_IMAGE}:${Tag}" `
    --push `
    ./wr-bot

if ($LASTEXITCODE -ne 0) { throw "Failed to build Discord Bot" }

Write-Host ""
Write-Host "[4/4] Building and pushing Frontend..." -ForegroundColor Yellow
docker buildx build `
    --platform linux/amd64 `
    -f infrastructure/docker/Dockerfile.frontend `
    -t "${FRONTEND}:${Tag}" `
    --push `
    ./frontend

if ($LASTEXITCODE -ne 0) { throw "Failed to build Frontend" }

Write-Host ""
Write-Host "================================" -ForegroundColor Green
Write-Host "All images pushed!"
Write-Host ""
Write-Host "Images:"
Write-Host "  - ${NEWS_SERVER}:${Tag}"
Write-Host "  - ${BOT_IMAGE}:${Tag}"
Write-Host "  - ${FRONTEND}:${Tag}"
Write-Host ""
Write-Host "On your server, run:"
Write-Host "  docker compose pull"
Write-Host "  docker compose up -d"
Write-Host "================================" -ForegroundColor Green
