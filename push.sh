#!/bin/bash
set -e

NEWS_SERVER="wign/news-server"
BOT_IMAGE="wign/bot-discord"
FRONTEND="wign/forex-frontend"
TAG="${1:-latest}"

echo "================================"
echo "Building and pushing Docker images"
echo "Tag: $TAG"
echo "================================"

echo ""
echo "[1/4] Setting up Docker buildx..."
docker buildx create --name multibuilder --driver docker-container --use 2>/dev/null || true
docker buildx inspect --bootstrap

echo ""
echo "[2/4] Building and pushing News Server..."
docker buildx build \
    --platform linux/amd64 \
    -f infrastructure/docker/Dockerfile.server \
    -t $NEWS_SERVER:$TAG \
    --push \
    ./news-server

echo ""
echo "[3/4] Building and pushing Discord Bot..."
docker buildx build \
    --platform linux/amd64 \
    -f infrastructure/docker/Dockerfile.bot \
    -t $BOT_IMAGE:$TAG \
    --push \
    ./wr-bot

echo ""
echo "[4/4] Building and pushing Frontend..."
docker buildx build \
    --platform linux/amd64 \
    -f infrastructure/docker/Dockerfile.frontend \
    -t $FRONTEND:$TAG \
    --push \
    ./frontend

echo ""
echo "================================"
echo "All images pushed!"
echo ""
echo "Images:"
echo "  - $NEWS_SERVER:$TAG"
echo "  - $BOT_IMAGE:$TAG"
echo "  - $FRONTEND:$TAG"
echo ""
echo "On your server, run:"
echo "  docker compose pull"
echo "  docker compose up -d"
echo "================================"
