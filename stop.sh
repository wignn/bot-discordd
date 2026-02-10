#!/bin/bash
set -e

BLUE='\033[0;34m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "\n========== Stopping Services ==========\n"

echo -e "${BLUE}[INFO]${NC} Stopping Discord bot..."; docker compose stop discord-bot 2>/dev/null || true; sleep 2
echo -e "${BLUE}[INFO]${NC} Stopping News Server..."; docker compose stop news-server 2>/dev/null || true; sleep 2
echo -e "${BLUE}[INFO]${NC} Stopping PostgreSQL..."; docker compose stop postgres 2>/dev/null || true

echo ""; echo -e "${GREEN}[OK]${NC} All services stopped!"; echo ""
docker compose ps
