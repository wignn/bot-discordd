# Fio

Real-time forex news monitoring with automatic Discord notifications.

## Architecture

![System Architecture](./architecture.svg)

<!-- ```
RSS Feeds ─┐
Stock Feeds ┤     ┌──────────────┐    WebSocket    ┌─────────────┐
Calendar ───┴────>│ News Server  │────────────────>│ Discord Bot │
                  │    (Go)      │                 │   (Rust)    │
                  └──────┬───────┘                 └─────────────┘
                         │
                  ┌──────┴───────┐
                  │  PostgreSQL  │
                  └──────────────┘
``` -->

Single Go binary handles RSS collection, article scraping, WebSocket broadcasting, and REST API.

## Tech Stack

| Component | Technology |
|-----------|------------|
| News Server | Go 1.24 (gorilla/websocket, pgx, goquery, gofeed) |
| Discord Bot | Rust (Serenity, Poise, SQLx, tokio-tungstenite) |
| Database | PostgreSQL 16 |
| Frontend | Next.js |

## Project Structure

```
forex/
├── docker-compose.yml
├── push.ps1 / push.sh
├── start.ps1 / start.sh
├── stop.ps1 / stop.sh
│
├── infrastructure/docker/
│   ├── Dockerfile.server
│   ├── Dockerfile.bot
│   └── Dockerfile.frontend
│
├── news-server/                     # Go
│   ├── main.go
│   └── internal/
│       ├── config/config.go
│       ├── database/postgres.go
│       ├── api/
│       │   ├── server.go            # HTTP server + CORS
│       │   ├── middleware.go         # API key auth
│       │   ├── news.go              # /api/v1/news endpoints
│       │   └── stock.go             # /api/v1/stock endpoints
│       ├── ws/
│       │   ├── hub.go               # WebSocket connection manager
│       │   └── events.go            # Discord embed builders
│       ├── collector/
│       │   ├── rss.go
│       │   ├── stock.go
│       │   └── calendar.go
│       ├── scraper/article.go
│       ├── pipeline/
│       │   ├── news.go
│       │   ├── stock.go
│       │   └── calendar.go
│       └── htmlutil/clean.go
│
├── wr-bot/                          # Rust
│   ├── Cargo.toml
│   └── src/
│
└── frontend/                        # Next.js
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| news-server | 8000 | Go: RSS collection, scraping, REST API, WebSocket |
| discord-bot | - | Rust: Discord notifications, commands, music |
| postgres | 5432 | PostgreSQL database |
| frontend | 3000 | Web dashboard |
| pgweb | 8081 | DB admin (admin profile only) |

## Discord Commands

| Command | Description |
|---------|-------------|
| `/forex_setup #channel` | Setup forex news |
| `/forex_disable` | Disable forex news |
| `/forex_enable` | Re-enable forex news |
| `/forex_status` | Check status |
| `/forex_calendar` | View high-impact events |
| `/calendar_setup #channel` | Setup calendar reminders |
| `/calendar_disable` | Disable reminders |
| `/calendar_enable` | Re-enable reminders |
| `/calendar_status` | Check status |
| `/calendar_mention true/false` | Toggle @everyone |
| `/stocknews #channel` | Setup stock news |

## Setup

```bash
git clone https://github.com/wignn/bot-discordd.git
cd bot-discordd

cp wr-bot/.env.example wr-bot/.env
# edit wr-bot/.env with your Discord token, Gemini key, etc.

docker compose up -d
```

## Configuration

### Discord Bot (`wr-bot/.env`)

```env
DISCORD_TOKEN=...
DATABASE_URL=postgres://postgres:postgres@postgres:5432/forex
NEWS_WS_URL=ws://news-server:8000
GEMINI_API_KEY=...
```

### News Server (docker-compose environment)

```env
DATABASE_URL=postgres://postgres:postgres@postgres:5432/forex
PORT=8000
API_KEYS=key1,key2          # comma-separated, leave empty to disable auth
LOG_LEVEL=INFO
```

## API

### REST

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /health | Health check |
| GET | /api/v1/news | List articles (paginated) |
| GET | /api/v1/news/latest | Latest articles |
| GET | /api/v1/news/{id} | Single article |
| GET | /api/v1/stock/latest | Latest stock news |

### WebSocket

Connect: `ws://host:8000/api/v1/stream/ws?bot_id=mybot`

Events: `news.new`, `news.high_impact`, `stock.news.new`, `calendar.reminder`

## Deployment

```bash
# build & push
./push.ps1 latest    # windows
./push.sh latest     # linux

# on server
docker compose pull
docker compose up -d
```

## RSS Feeds

| Name | Category |
|------|----------|
| InvestingLive | Forex |
| FXStreet | Forex |
| Investing.com Forex | Forex |
| Investing.com Economic | Economic |
| Federal Reserve | Central Bank |
| ECB | Central Bank |
| CNBC Indonesia | Stock |
| Tempo.co | Stock |

## License

MIT License - see [LICENSE](LICENSE).
