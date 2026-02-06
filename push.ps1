param(
    [string]$Tag = "latest"
)

$ErrorActionPreference = "Stop"

$BOT_IMAGE = "wign/bot-discord"
$NEWS_API_IMAGE = "wign/news-server"
$NEWS_WORKER_IMAGE = "wign/news-worker"
$FOREX_FRONTEND = "wign/forex-frontend"

Write-Host "================================" -ForegroundColor Cyan
Write-Host "Building and pushing Docker images"
Write-Host "Tag: $Tag"
Write-Host "================================" -ForegroundColor Cyan

Write-Host ""
Write-Host "[1/5] Setting up Docker buildx..." -ForegroundColor Yellow
docker buildx create --name multibuilder --driver docker-container --use 2>$null
docker buildx inspect --bootstrap

Write-Host ""
Write-Host "[2/5] Building and pushing Discord Bot..." -ForegroundColor Yellow
docker buildx build `
    --platform linux/amd64 `
    -f infrastructure/docker/Dockerfile.bot `
    -t "${BOT_IMAGE}:${Tag}" `
    --push `
    ./wr-bot

if ($LASTEXITCODE -ne 0) { throw "Failed to build Discord Bot" }

Write-Host ""
Write-Host "[3/5] Building and pushing News API..." -ForegroundColor Yellow
docker buildx build `
    --platform linux/amd64 `
    -f infrastructure/docker/Dockerfile.api `
    -t "${NEWS_API_IMAGE}:${Tag}" `
    --push `
    ./news-server

if ($LASTEXITCODE -ne 0) { throw "Failed to build News API" }

Write-Host ""
Write-Host "[4/5] Building and pushing News Worker..." -ForegroundColor Yellow
docker buildx build `
    --platform linux/amd64 `
    -f infrastructure/docker/Dockerfile.worker `
    -t "${NEWS_WORKER_IMAGE}:${Tag}" `
    --push `
    ./news-server

if ($LASTEXITCODE -ne 0) { throw "Failed to build News Worker" }

Write-Host ""
Write-Host "[5/5] Building and pushing frontend..." -ForegroundColor Yellow
docker buildx build `
    --platform linux/amd64 `
    -f infrastructure/docker/Dockerfile.frontend `
    -t "${FOREX_FRONTEND}:${Tag}" `
    --push `
    ./frontend

if ($LASTEXITCODE -ne 0) { throw "Failed to build Frontend" }

Write-Host ""
Write-Host "================================" -ForegroundColor Green
Write-Host "All images pushed successfully!"
Write-Host ""
Write-Host "Images:"
Write-Host "  - ${BOT_IMAGE}:${Tag}"
Write-Host "  - ${NEWS_API_IMAGE}:${Tag}"
Write-Host "  - ${NEWS_WORKER_IMAGE}:${Tag}"
Write-Host "  - ${FOREX_FRONTEND}:${Tag}"
Write-Host ""
Write-Host "On your server, run:"
Write-Host "  docker compose pull"
Write-Host "  docker compose up -d"
Write-Host "================================" -ForegroundColor Green
