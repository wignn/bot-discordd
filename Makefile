IMAGE_NAME = wign/bot-discord
IMAGE_TAG = latest
NEWS_IMAGE = wign/news-server
NEWS_TAG = latest

run:
	set AUDIOPUS_SYS_USE_PKG_CONFIG=1 && cargo run

dev:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

build:
	docker build -f infrastructure/docker/Dockerfile.bot -t $(IMAGE_NAME):$(IMAGE_TAG) ./wr-bot

build-multi:
	docker buildx build --platform linux/amd64,linux/arm64 -f infrastructure/docker/Dockerfile.bot -t $(IMAGE_NAME):$(IMAGE_TAG) --push ./wr-bot

build-amd64:
	docker buildx build --platform linux/amd64 -f infrastructure/docker/Dockerfile.bot -t $(IMAGE_NAME):$(IMAGE_TAG) --push ./wr-bot

build-arm64:
	docker buildx build --platform linux/arm64 -f infrastructure/docker/Dockerfile.bot -t $(IMAGE_NAME):$(IMAGE_TAG) --push ./wr-bot

push:
	docker push $(IMAGE_NAME):$(IMAGE_TAG)

build-news:
	docker build -f infrastructure/docker/Dockerfile.api -t $(NEWS_IMAGE):$(NEWS_TAG) ./news-server

build-news-multi:
	docker buildx build --platform linux/amd64,linux/arm64 -f infrastructure/docker/Dockerfile.api -t $(NEWS_IMAGE):$(NEWS_TAG) --push ./news-server

build-news-amd64:
	docker buildx build --platform linux/amd64 -f infrastructure/docker/Dockerfile.api -t $(NEWS_IMAGE):$(NEWS_TAG) --push ./news-server

build-news-arm64:
	docker buildx build --platform linux/arm64 -f infrastructure/docker/Dockerfile.api -t $(NEWS_IMAGE):$(NEWS_TAG) --push ./news-server

push-news:
	docker push $(NEWS_IMAGE):$(NEWS_TAG)

build-all: build build-news
push-all: push push-news
build-all-multi: build-multi build-news-multi

setup-buildx:
	docker buildx create --name multibuilder --driver docker-container --use || true
	docker buildx inspect --bootstrap

clean:
	docker compose down -v --rmi local
	docker system prune -f

help:
	@echo "Available commands:"
	@echo "  make run              - Run locally with cargo"
	@echo "  make dev              - Run with docker compose (build + up)"
	@echo "  make down             - Stop docker compose"
	@echo "  make logs             - View docker compose logs"
	@echo ""
	@echo "Discord Bot:"
	@echo "  make build            - Build bot image for current platform"
	@echo "  make build-multi      - Build and push bot for amd64 + arm64"
	@echo "  make build-amd64      - Build and push bot for amd64 only"
	@echo "  make push             - Push bot image to Docker Hub"
	@echo ""
	@echo "News Server:"
	@echo "  make build-news       - Build news image for current platform"
	@echo "  make build-news-multi - Build and push news for amd64 + arm64"
	@echo "  make build-news-amd64 - Build and push news for amd64 only"
	@echo "  make push-news        - Push news image to Docker Hub"
	@echo ""
	@echo "All:"
	@echo "  make build-all        - Build both images"
	@echo "  make push-all         - Push both images"
	@echo "  make build-all-multi  - Build and push both for multi-platform"
	@echo ""
	@echo "  make setup-buildx     - Setup buildx for multi-platform builds"
	@echo "  make clean            - Clean up docker resources"

.PHONY: run dev down logs build build-multi build-amd64 build-arm64 push build-news build-news-multi build-news-amd64 build-news-arm64 push-news build-all push-all build-all-multi setup-buildx clean help

