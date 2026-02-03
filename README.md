# Forex News Discord Bot

A comprehensive forex news monitoring and Discord bot platform with real-time news aggregation, AI-powered analysis, and automated notifications.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Services](#services)
- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [API Documentation](#api-documentation)

---

## Overview

This platform consists of two main components:

1. **News Server** - A Python-based backend service that collects, processes, and distributes forex news
2. **Discord Bot** - A Rust-based Discord bot that delivers real-time news alerts and provides trading-related commands

The system automatically scrapes forex news from multiple sources, processes them using AI for translation, sentiment analysis, and impact assessment, then broadcasts the processed news to connected Discord servers via WebSocket.

---

## Architecture

```
                                    +------------------+
                                    |   Discord API    |
                                    +--------+---------+
                                             |
                                             v
+----------------+              +------------+------------+
|  RSS Sources   |              |     Discord Bot        |
|  News Websites |              |       (Rust)           |
+-------+--------+              +------------+------------+
        |                                    |
        v                                    | WebSocket
+-------+--------+              +------------v------------+
|  News Worker   |   RabbitMQ   |      News API          |
|   (Celery)     +<------------>+      (FastAPI)         |
+-------+--------+              +------------+------------+
        |                                    |
        v                                    v
+-------+--------+              +------------+------------+
|  AI Providers  |              |      PostgreSQL        |
|  (Gemini/Groq) |              |        Redis           |
+----------------+              +-------------------------+
```

### Data Flow

1. **Collection**: Celery workers periodically fetch news from RSS feeds and web scrapers
2. **Processing**: AI providers analyze articles for sentiment, extract entities, and translate to Indonesian
3. **Storage**: Processed articles are stored in PostgreSQL
4. **Distribution**: News API broadcasts via WebSocket to connected Discord bots
5. **Notification**: Discord bot sends formatted embeds to subscribed channels

---

## Tech Stack

### Discord Bot (Rust)

| Component | Technology | Purpose |
|-----------|------------|---------|
| Runtime | Rust 2024 Edition | High-performance, memory-safe execution |
| Discord Framework | Serenity 0.12 + Poise 0.6 | Discord API interaction and command handling |
| Database | SQLx + PostgreSQL | Async database operations |
| WebSocket | tokio-tungstenite | Real-time news stream connection |
| Music | Songbird + Lavalink | Audio streaming and playback |
| AI | gemini-rust | Google Gemini integration |
| HTTP | Reqwest | REST API calls |
| Async Runtime | Tokio | Asynchronous task execution |

### News Server (Python)

| Component | Technology | Purpose |
|-----------|------------|---------|
| Web Framework | FastAPI | REST API and WebSocket server |
| Task Queue | Celery | Distributed task processing |
| Message Broker | RabbitMQ | Task queue messaging |
| Cache | Redis | Caching and Celery result backend |
| Database | PostgreSQL + SQLAlchemy | Data persistence with async support |
| ORM | SQLAlchemy 2.0 + asyncpg | Async database operations |
| Web Scraping | BeautifulSoup, Playwright, newspaper3k | Content extraction |
| RSS | feedparser | RSS feed parsing |
| AI Providers | Google Gemini, Groq, OpenAI | Text analysis and translation |
| Logging | structlog | Structured logging |

### Infrastructure

| Component | Technology | Purpose |
|-----------|------------|---------|
| Containerization | Docker | Service isolation |
| Orchestration | Docker Compose | Multi-container management |
| Database | PostgreSQL 16 | Primary data store |
| Cache | Redis 7 | Session and cache storage |
| Message Queue | RabbitMQ 3 | Task distribution |
| Music Server | Lavalink 4 | Audio streaming backend |
| Monitoring | Flower | Celery task monitoring |
| DB Admin | pgweb | Database web interface |

---

## Project Structure

```
forex/
├── docker-compose.yml          # Main orchestration file
├── Makefile                    # Build automation
├── push.ps1                    # Docker push script (Windows)
├── push.sh                     # Docker push script (Linux)
│
├── infrastructure/
│   └── docker/
│       ├── Dockerfile.api      # News API container
│       ├── Dockerfile.bot      # Discord bot container
│       └── Dockerfile.worker   # Celery worker container
│
├── news-server/                # Python news processing service
│   ├── app/
│   │   ├── main.py            # FastAPI application entry
│   │   ├── api/v1/            # API route handlers
│   │   ├── core/              # Configuration and logging
│   │   ├── db/                # Database session management
│   │   ├── models/            # SQLAlchemy models
│   │   ├── schemas/           # Pydantic schemas
│   │   └── websocket/         # WebSocket manager and events
│   │
│   └── workers/
│       ├── celery_app.py      # Celery configuration
│       ├── ai/                # AI processing modules
│       │   ├── translator.py  # News translation
│       │   ├── summarizer.py  # Article summarization
│       │   ├── sentiment_analyzer.py
│       │   ├── impact_analyzer.py
│       │   ├── entity_extractor.py
│       │   └── providers/     # AI provider implementations
│       ├── collectors/        # RSS and data collectors
│       ├── scrapers/          # Web scraping modules
│       └── tasks/             # Celery task definitions
│
└── wr-bot/                    # Rust Discord bot
    ├── Cargo.toml             # Rust dependencies
    ├── src/
    │   ├── main.rs            # Application entry point
    │   ├── lib.rs             # Library root
    │   ├── config.rs          # Configuration management
    │   ├── error.rs           # Error handling
    │   ├── commands/          # Slash command handlers
    │   │   ├── admin.rs       # Admin commands
    │   │   ├── ai.rs          # AI chat commands
    │   │   ├── forex.rs       # Forex-related commands
    │   │   ├── general.rs     # General utility commands
    │   │   ├── moderation.rs  # Moderation commands
    │   │   ├── music.rs       # Music playback commands
    │   │   └── price.rs       # Price lookup commands
    │   ├── handlers/          # Event handlers
    │   ├── repository/        # Database repositories
    │   └── services/          # External service integrations
    │       ├── gemini.rs      # Google Gemini AI
    │       ├── news_ws.rs     # News WebSocket client
    │       ├── tiingo.rs      # Market data API
    │       └── music/         # Music service modules
    │
    ├── migrations/            # SQL migration files
    └── lavalink/              # Lavalink configuration
```

---

## Services

### Core Services

| Service | Port | Description |
|---------|------|-------------|
| discord-bot | - | Discord bot application |
| news-api | 8000 | FastAPI REST and WebSocket server |
| news-worker | - | Celery task worker |
| news-beat | - | Celery periodic task scheduler |

### Infrastructure Services

| Service | Port | Description |
|---------|------|-------------|
| postgres | 5432 | PostgreSQL database |
| redis | 6379 | Redis cache and result backend |
| rabbitmq | 5672, 15672 | Message broker (AMQP + Management UI) |
| lavalink | 2333 | Audio streaming server |

### Monitoring Services

| Service | Port | Description |
|---------|------|-------------|
| flower | 5555 | Celery task monitoring dashboard |
| pgweb | 8081 | PostgreSQL web interface (admin profile) |

---

## Features

### News Processing

- Multi-source RSS feed collection
- Web scraping with Playwright for JavaScript-rendered content
- AI-powered article translation (English to Indonesian)
- Sentiment analysis (bullish/bearish/neutral)
- Impact level assessment
- Currency pair and entity extraction
- Automatic summarization

### Discord Bot

- Real-time forex news notifications
- Configurable alert channels per server
- High-impact news alerts with mentions
- Music playback with queue management
- AI chat integration
- Moderation tools (warn, kick, ban, timeout)
- Forex price lookups

### AI Providers

Supports multiple AI backends with automatic fallback:

- Google Gemini
- Groq
- OpenAI
- OpenRouter

---

## Installation

### Prerequisites

- Docker and Docker Compose v2
- Git

### Setup

1. Clone the repository:

```bash
git clone https://github.com/wignn/bot-discordd.git
cd bot-discordd
```

2. Create environment files:

```bash
# Discord bot environment
cp wr-bot/.env.example wr-bot/.env

# News server environment
cp news-server/.env.example news-server/.env
```

3. Configure environment variables (see Configuration section)

4. Start services:

```bash
docker compose up -d
```

5. Run database migrations:

```bash
docker compose exec discord-bot sqlx migrate run
```

---

## Configuration

### Discord Bot (.env)

```env
DISCORD_TOKEN=your_discord_bot_token
DATABASE_URL=postgres://postgres:postgres@postgres:5432/forex
NEWS_WS_URL=ws://news-api:8000
LAVALINK_HOST=lavalink
LAVALINK_PORT=2333
LAVALINK_PASSWORD=youshallnotpass
GEMINI_API_KEY=your_gemini_api_key
```

### News Server (.env)

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/forex
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=amqp://guest:guest@rabbitmq:5672//
CELERY_RESULT_BACKEND=redis://redis:6379/1
AI_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key
GROQ_API_KEY=your_groq_api_key
```

---

## Deployment

### Building Images

```bash
# Build all images
docker compose build

# Or build individually
docker compose build discord-bot
docker compose build news-api
docker compose build news-worker
```

### Pushing to Registry

Windows:
```powershell
./push.ps1 latest
```

Linux:
```bash
./push.sh latest
```

### Production Deployment

1. Set appropriate environment variables for production
2. Configure external PostgreSQL and Redis instances
3. Set up reverse proxy (nginx/traefik) for news-api
4. Configure SSL certificates
5. Adjust resource limits in docker-compose.yml

---

## API Documentation

### REST Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/health | Health check |
| GET | /api/v1/articles | List processed articles |
| POST | /api/v1/stream/ws/broadcast-article | Internal broadcast endpoint |

### WebSocket

Connect to `/api/v1/stream/ws/discord?bot_id={bot_id}` for real-time news events.

Event types:
- `news.new` - New article processed
- `news.high_impact` - High impact news alert
- `sentiment.alert` - Sentiment shift notification
- `connected` - Connection established
- `heartbeat` - Keep-alive ping

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
