IMAGE_BOT = wign/bot-discord
IMAGE_SERVER = wign/news-server
IMAGE_FRONTEND = wign/forex-frontend
TAG = latest

dev:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

build-server:
	docker build -f infrastructure/docker/Dockerfile.server -t $(IMAGE_SERVER):$(TAG) ./news-server

build-bot:
	docker build -f infrastructure/docker/Dockerfile.bot -t $(IMAGE_BOT):$(TAG) ./wr-bot

build-frontend:
	docker build -f infrastructure/docker/Dockerfile.frontend -t $(IMAGE_FRONTEND):$(TAG) ./frontend

build-all: build-server build-bot build-frontend

push-server:
	docker push $(IMAGE_SERVER):$(TAG)

push-bot:
	docker push $(IMAGE_BOT):$(TAG)

push-frontend:
	docker push $(IMAGE_FRONTEND):$(TAG)

push-all: push-server push-bot push-frontend

build-server-amd64:
	docker buildx build --platform linux/amd64 -f infrastructure/docker/Dockerfile.server -t $(IMAGE_SERVER):$(TAG) --push ./news-server

build-bot-amd64:
	docker buildx build --platform linux/amd64 -f infrastructure/docker/Dockerfile.bot -t $(IMAGE_BOT):$(TAG) --push ./wr-bot

build-all-amd64: build-server-amd64 build-bot-amd64

setup-buildx:
	docker buildx create --name multibuilder --driver docker-container --use || true
	docker buildx inspect --bootstrap

clean:
	docker compose down -v --rmi local
	docker system prune -f

help:
	@echo "Available commands:"
	@echo "  make dev              - Run with docker compose"
	@echo "  make down             - Stop docker compose"
	@echo "  make logs             - View logs"
	@echo ""
	@echo "Build:"
	@echo "  make build-server     - Build news server image"
	@echo "  make build-bot        - Build discord bot image"
	@echo "  make build-frontend   - Build frontend image"
	@echo "  make build-all        - Build all images"
	@echo ""
	@echo "Push:"
	@echo "  make push-server      - Push news server"
	@echo "  make push-bot         - Push discord bot"
	@echo "  make push-all         - Push all images"
	@echo ""
	@echo "  make setup-buildx     - Setup buildx"
	@echo "  make clean            - Clean docker resources"

.PHONY: dev down logs build-server build-bot build-frontend build-all push-server push-bot push-frontend push-all build-server-amd64 build-bot-amd64 build-all-amd64 setup-buildx clean help
