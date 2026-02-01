# push.ps1 - Build and push all images to Docker Hub (PowerShell)

param(
    [string]$Tag = "latest"
)

$ErrorActionPreference = "Stop"

# Configuration
$BOT_IMAGE = "wign/bot-discord"
$NEWS_API_IMAGE = "wign/news-server"
$NEWS_WORKER_IMAGE = "wign/news-worker"

Write-Host "================================" -ForegroundColor Cyan
Write-Host "Building and pushing Docker images"
Write-Host "Tag: $Tag"
Write-Host "================================" -ForegroundColor Cyan

# Setup buildx if not exists
Write-Host ""
Write-Host "[1/4] Setting up Docker buildx..." -ForegroundColor Yellow
docker buildx create --name multibuilder --driver docker-container --use 2>$null
docker buildx inspect --bootstrap

# Build and push Discord Bot
Write-Host ""
Write-Host "[2/4] Building and pushing Discord Bot..." -ForegroundColor Yellow
docker buildx build `
    --platform linux/amd64 `
    -f infrastructure/docker/Dockerfile.bot `
    -t "${BOT_IMAGE}:${Tag}" `
    --push `
    ./wr-bot

if ($LASTEXITCODE -ne 0) { throw "Failed to build Discord Bot" }

# Build and push News API
Write-Host ""
Write-Host "[3/4] Building and pushing News API..." -ForegroundColor Yellow
docker buildx build `
    --platform linux/amd64 `
    -f infrastructure/docker/Dockerfile.api `
    -t "${NEWS_API_IMAGE}:${Tag}" `
    --push `
    ./news-server

if ($LASTEXITCODE -ne 0) { throw "Failed to build News API" }

# Build and push News Worker
Write-Host ""
Write-Host "[4/4] Building and pushing News Worker..." -ForegroundColor Yellow
docker buildx build `
    --platform linux/amd64 `
    -f infrastructure/docker/Dockerfile.worker `
    -t "${NEWS_WORKER_IMAGE}:${Tag}" `
    --push `
    ./news-server

if ($LASTEXITCODE -ne 0) { throw "Failed to build News Worker" }

Write-Host ""
Write-Host "================================" -ForegroundColor Green
Write-Host "All images pushed successfully!"
Write-Host ""
Write-Host "Images:"
Write-Host "  - ${BOT_IMAGE}:${Tag}"
Write-Host "  - ${NEWS_API_IMAGE}:${Tag}"
Write-Host "  - ${NEWS_WORKER_IMAGE}:${Tag}"
Write-Host ""
Write-Host "On your server, run:"
Write-Host "  docker compose pull"
Write-Host "  docker compose up -d"
Write-Host "================================" -ForegroundColor Green
