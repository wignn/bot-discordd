#!/bin/bash
# push.sh - Build and push all images to Docker Hub

set -e

# Configuration
BOT_IMAGE="wign/bot-discord"
NEWS_API_IMAGE="wign/news-server"
NEWS_WORKER_IMAGE="wign/news-worker"
TAG="${1:-latest}"

echo "================================"
echo "Building and pushing Docker images"
echo "Tag: $TAG"
echo "================================"

# Setup buildx if not exists
echo ""
echo "[1/4] Setting up Docker buildx..."
docker buildx create --name multibuilder --driver docker-container --use 2>/dev/null || true
docker buildx inspect --bootstrap

# Build and push Discord Bot
echo ""
echo "[2/4] Building and pushing Discord Bot..."
docker buildx build \
    --platform linux/amd64 \
    -f infrastructure/docker/Dockerfile.bot \
    -t $BOT_IMAGE:$TAG \
    --push \
    ./wr-bot

# Build and push News API
echo ""
echo "[3/4] Building and pushing News API..."
docker buildx build \
    --platform linux/amd64 \
    -f infrastructure/docker/Dockerfile.api \
    -t $NEWS_API_IMAGE:$TAG \
    --push \
    ./news-server

# Build and push News Worker
echo ""
echo "[4/4] Building and pushing News Worker..."
docker buildx build \
    --platform linux/amd64 \
    -f infrastructure/docker/Dockerfile.worker \
    -t $NEWS_WORKER_IMAGE:$TAG \
    --push \
    ./news-server

echo ""
echo "================================"
echo "✅ All images pushed successfully!"
echo ""
echo "Images:"
echo "  - $BOT_IMAGE:$TAG"
echo "  - $NEWS_API_IMAGE:$TAG"
echo "  - $NEWS_WORKER_IMAGE:$TAG"
echo ""
echo "On your server, run:"
echo "  docker compose pull"
echo "  docker compose up -d"
echo "================================"
