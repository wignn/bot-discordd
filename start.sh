#!/bin/bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[OK]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

wait_for_healthy() {
    local container=$1
    local max_attempts=${2:-30}
    local attempt=1
    print_status "Waiting for $container..."
    while [ $attempt -le $max_attempts ]; do
        status=$(docker inspect --format='{{.State.Health.Status}}' $container 2>/dev/null || echo "not_found")
        if [ "$status" = "healthy" ]; then print_success "$container is healthy"; return 0; fi
        if [ "$status" = "not_found" ]; then print_error "$container not found"; return 1; fi
        echo -n "."; sleep 2; attempt=$((attempt + 1))
    done
    echo ""; print_status "$container did not become healthy in time, continuing..."; return 0
}

wait_for_running() {
    local container=$1
    local max_attempts=${2:-15}
    local attempt=1
    print_status "Waiting for $container..."
    while [ $attempt -le $max_attempts ]; do
        status=$(docker inspect --format='{{.State.Status}}' $container 2>/dev/null || echo "not_found")
        if [ "$status" = "running" ]; then print_success "$container is running"; return 0; fi
        echo -n "."; sleep 1; attempt=$((attempt + 1))
    done
    echo ""; print_error "$container failed to start"; return 1
}

echo -e "\n========== Starting Services ==========\n"

print_status "PHASE 1: Database"
docker compose up -d postgres; wait_for_healthy "forex-postgres" 60; sleep 3
print_success "Database OK\n"

print_status "PHASE 2: News Server"
docker compose up -d news-server; wait_for_running "news-server" 30; sleep 3
print_success "News Server OK\n"

print_status "PHASE 3: Discord Bot"
docker compose up -d discord-bot; wait_for_running "bot-discord" 30; sleep 3
print_success "Bot OK\n"

echo "========== All Services Started =========="
docker compose ps
echo -e "\nNews Server: http://localhost:8000/health"
