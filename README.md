# Fio - Forex News Discord Bot

Real-time forex news monitoring platform with automatic Discord notifications and economic calendar reminders.

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

1. **News Server** - Python backend service for collecting and distributing forex news
2. **Discord Bot** - Rust-based Discord bot for real-time news notifications

The system automatically scrapes forex news from multiple sources and broadcasts them to Discord servers via WebSocket. Translation is available via a separate endpoint for manual use.

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
|  Broadcast     |              |      PostgreSQL        |
|  (Direct)      |              |        Redis           |
+----------------+              +-------------------------+
```

### Data Flow

1. **Collection**: Celery workers fetch news from RSS feeds
2. **Processing**: Articles are processed and stored (no AI to save costs)
3. **Storage**: Articles saved to PostgreSQL
4. **Distribution**: News API broadcasts via WebSocket to Discord bots
5. **Notification**: Discord bot sends embeds to configured channels

---

## Tech Stack

### Discord Bot (Rust)

| Component | Technology | Purpose |
|-----------|------------|---------|
| Runtime | Rust 2024 Edition | High-performance execution |
| Discord Framework | Serenity 0.12 + Poise 0.6 | Discord API interaction |
| Database | SQLx + PostgreSQL | Async database operations |
| WebSocket | tokio-tungstenite | Real-time news stream |
| Music | Songbird + Lavalink | Audio streaming |
| HTTP | Reqwest | REST API calls |
| Async Runtime | Tokio | Async task execution |

### News Server (Python)

| Component | Technology | Purpose |
|-----------|------------|---------|
| Web Framework | FastAPI | REST API and WebSocket server |
| Task Queue | Celery | Distributed task processing |
| Message Broker | RabbitMQ | Task queue messaging |
| Cache | Redis | Caching and Celery result backend |
| Database | PostgreSQL + SQLAlchemy | Data persistence |
| Web Scraping | BeautifulSoup, Playwright | Content extraction |
| RSS | feedparser | RSS feed parsing |
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

---

## Project Structure

```
forex/
├── docker-compose.yml
├── Makefile
├── push.ps1
├── push.sh
│
├── infrastructure/
│   └── docker/
│       ├── Dockerfile.api
│       ├── Dockerfile.bot
│       └── Dockerfile.worker
│
├── news-server/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/v1/
│   │   │   └── endpoints/
│   │   │       ├── news.py
│   │   │       ├── translate.py
│   │   │       ├── sources.py
│   │   │       ├── analytics.py
│   │   │       ├── search.py
│   │   │       └── websocket.py
│   │   ├── core/
│   │   ├── db/
│   │   ├── models/
│   │   ├── schemas/
│   │   └── websocket/
│   │
│   └── workers/
│       ├── celery_app.py
│       ├── collectors/
│       │   ├── rss_collector.py
│       │   ├── stock_id_collector.py
│       │   └── calendar_collector.py
│       ├── scrapers/
│       └── tasks/
│           ├── broadcast_tasks.py
│           ├── calendar_tasks.py
│           ├── collection_tasks.py
│           ├── scraping_tasks.py
│           ├── stock_tasks.py
│           └── websocket_tasks.py
│
└── wr-bot/
    ├── Cargo.toml
    ├── src/
    │   ├── main.rs
    │   ├── commands/
    │   │   ├── admin.rs
    │   │   ├── ai.rs
    │   │   ├── calendar.rs
    │   │   ├── chart.rs
    │   │   ├── forex.rs
    │   │   ├── general.rs
    │   │   ├── moderation.rs
    │   │   ├── music.rs
    │   │   ├── price.rs
    │   │   └── stock.rs
    │   ├── handlers/
    │   ├── repository/
    │   │   ├── calendar.rs
    │   │   ├── forex.rs
    │   │   ├── moderation.rs
    │   │   └── stock.rs
    │   └── services/
    │       ├── news_ws.rs
    │       ├── tiingo.rs
    │       └── music/
    │
    ├── migrations/
    └── lavalink/
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
| redis | 6379 | Redis cache |
| rabbitmq | 5672, 15672 | Message broker |
| lavalink | 2333 | Audio streaming server |

---

## Features

### News Processing

- Multi-source RSS feed collection (InvestingLive, FXStreet, Investing.com, etc)
- Web scraping with Playwright for JavaScript-rendered content
- Direct broadcast to Discord
- Translation endpoint available for manual use

### Discord Bot (Fio)

- Real-time forex news notifications
- Economic calendar reminders (15 min before high-impact events)
- Separate channels for news and calendar
- WIB timezone support for calendar events
- Music playback with queue management
- AI chat integration (Gemini)
- Moderation tools (warn, kick, ban, timeout)
- Forex price lookups and charts
- Stock news notifications

### Discord Commands

| Command | Description |
|---------|-------------|
| `/forex_setup #channel` | Setup forex news notifications |
| `/forex_disable` | Disable forex news |
| `/forex_enable` | Re-enable forex news |
| `/forex_status` | Check forex news status |
| `/forex_calendar` | View high-impact events |
| `/calendar_setup #channel` | Setup calendar reminders (separate channel) |
| `/calendar_disable` | Disable calendar reminders |
| `/calendar_enable` | Re-enable calendar reminders |
| `/calendar_status` | Check calendar status |
| `/calendar_mention true/false` | Toggle @everyone for events |
| `/stocknews #channel` | Setup stock news notifications |
| `/price SYMBOL` | Get current forex price |
| `/chart SYMBOL` | Get forex chart |

### Translation Endpoint

Separate endpoint available for manual translation:

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/translate/text | Translate plain text |
| POST | /api/v1/translate/article | Translate article (same structure as news) |
| GET | /api/v1/translate/providers | List available providers |

Supported providers: Gemini, Groq, OpenRouter

---

## Installation

### Prerequisites

- Docker and Docker Compose v2
- Git

### Setup

1. Clone repository:

```bash
git clone https://github.com/wignn/bot-discordd.git
cd bot-discordd
```

2. Create environment files:

```bash
cp wr-bot/.env.example wr-bot/.env
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
FOREX_SERVICE_URL=http://news-api:8000
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

# Optional - for translation endpoint
AI_PRIMARY_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key
GROQ_API_KEY=your_groq_api_key
OPENROUTER_API_KEY=your_openrouter_api_key
```

---

## Deployment

### Building Images

```bash
docker compose build
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

1. Set environment variables for production
2. Configure external PostgreSQL and Redis
3. Set up reverse proxy (nginx/traefik)
4. Configure SSL certificates
5. Adjust resource limits in docker-compose.yml

---

## API Documentation

### REST Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/health | Health check |
| GET | /api/v1/news | List articles |
| POST | /api/v1/translate/text | Translate text |
| POST | /api/v1/translate/article | Translate article |
| GET | /api/v1/translate/providers | List AI providers |
| POST | /api/v1/stream/ws/broadcast-article | Internal broadcast |

### WebSocket

Connect to `/api/v1/stream/ws/discord?bot_id={bot_id}` for real-time events.

Event types:
- `news.new` - New article
- `news.high_impact` - High impact news alert
- `stock.news.new` - Stock news article
- `calendar.reminder` - Economic calendar reminder
- `connected` - Connection established
- `heartbeat` - Keep-alive ping

---

## RSS Feeds

Default configured feeds:

| Name | Category | URL |
|------|----------|-----|
| InvestingLive | Forex | investinglive.com/feed/news |
| FXStreet | Forex | fxstreet-id.com/rss/news |
| Investing.com Forex | Forex | id.investing.com/rss/news_301.rss |
| Investing.com Economic | Economic | id.investing.com/rss/news_95.rss |
| Federal Reserve | Central Bank | federalreserve.gov/feeds/press_all.xml |
| ECB | Central Bank | ecb.europa.eu/rss/press.html |

---

## License

MIT License - see [LICENSE](LICENSE) file.
