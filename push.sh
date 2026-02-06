#!/bin/bash

set -e

BOT_IMAGE="wign/bot-discord"
NEWS_API_IMAGE="wign/news-server"
NEWS_WORKER_IMAGE="wign/news-worker"
FOREX_FRONTEND="wign/forex-frontend"
TAG="${1:-latest}"

echo "================================"
echo "Building and pushing Docker images"
echo "Tag: $TAG"
echo "================================"

echo ""
echo "[1/5] Setting up Docker buildx..."
docker buildx create --name multibuilder --driver docker-container --use 2>/dev/null || true
docker buildx inspect --bootstrap

echo ""
echo "[2/5] Building and pushing Discord Bot..."
docker buildx build \
    --platform linux/amd64 \
    -f infrastructure/docker/Dockerfile.bot \
    -t $BOT_IMAGE:$TAG \
    --push \
    ./wr-bot

echo ""
echo "[3/5] Building and pushing News API..."
docker buildx build \
    --platform linux/amd64 \
    -f infrastructure/docker/Dockerfile.api \
    -t $NEWS_API_IMAGE:$TAG \
    --push \
    ./news-server

echo ""
echo "[4/5] Building and pushing News Worker..."
docker buildx build \
    --platform linux/amd64 \
    -f infrastructure/docker/Dockerfile.worker \
    -t $NEWS_WORKER_IMAGE:$TAG \
    --push \
    ./news-server

echo ""
echo "[5/5] Building and pushing frontend..."
docker buildx build \
    --platform linux/amd64 \
    -f infrastructure/docker/Dockerfile.frontend \
    -t $FOREX_FRONTEND:$TAG \
    --push \
    ./news-server

echo ""
echo "================================"
echo "All images pushed successfully!"
echo ""
echo "Images:"
echo "  - $BOT_IMAGE:$TAG"
echo "  - $NEWS_API_IMAGE:$TAG"
echo "  - $NEWS_WORKER_IMAGE:$TAG"
echo "  - $FOREX_FRONTEND:$TAG"
echo ""
echo "On your server, run:"
echo "  docker compose pull"
echo "  docker compose up -d"
echo "================================"
