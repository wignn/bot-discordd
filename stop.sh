#!/bin/bash
set -e

BLUE='\033[0;34m'
GREEN='\033[0;32m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[OK]${NC} $1"; }

echo -e "\n========== Stopping Services ==========\n"

print_status "Stopping Discord bot..."; docker compose stop discord-bot 2>/dev/null || true; sleep 2
print_status "Stopping Lavalink..."; docker compose stop lavalink 2>/dev/null || true; sleep 2
print_status "Stopping Flower..."; docker compose stop flower 2>/dev/null || true
print_status "Stopping Celery beat..."; docker compose stop news-beat 2>/dev/null || true
print_status "Stopping Celery worker..."; docker compose stop news-worker 2>/dev/null || true; sleep 2
print_status "Stopping News API..."; docker compose stop news-api 2>/dev/null || true; sleep 2
print_status "Stopping RabbitMQ..."; docker compose stop rabbitmq 2>/dev/null || true
print_status "Stopping Redis..."; docker compose stop redis 2>/dev/null || true
print_status "Stopping PostgreSQL..."; docker compose stop postgres 2>/dev/null || true

echo ""; print_success "All services stopped!"; echo ""
docker compose ps
