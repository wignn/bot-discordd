# Forex Service API Documentation

## Overview

The Forex Service provides real-time forex price data, chart generation, technical analysis, and price alerts. It connects to Tiingo's WebSocket API for live price updates and exposes both REST API and WebSocket interfaces.

## Architecture

```
┌─────────────────┐       ┌──────────────────────────────────┐
│   Discord Bot   │       │      Python Forex Service        │
│   (Rust)        │       │      (FastAPI)                   │
├─────────────────┤       ├──────────────────────────────────┤
│ - Commands UI   │◄─────►│ - Tiingo WebSocket (data source) │
│ - Embed display │  WS   │ - Price caching (in-memory)      │
│ - Alert notify  │  +    │ - OHLC aggregation               │
│                 │  REST │ - Chart generation (matplotlib)  │
│                 │       │ - Technical indicators           │
│                 │       │ - Alert management               │
└─────────────────┘       └──────────────────────────────────┘
```

## REST API Endpoints

### Prices

#### Get Price
```http
GET /api/v1/forex/price/{symbol}
```

**Response:**
```json
{
  "symbol": "EURUSD",
  "bid": 1.08234,
  "ask": 1.08237,
  "mid": 1.082355,
  "spread": 0.00003,
  "spread_pips": 0.3,
  "timestamp": "2026-02-03T10:30:00Z"
}
```

#### Get All Prices
```http
GET /api/v1/forex/prices
```

**Response:**
```json
{
  "prices": [...],
  "count": 45,
  "timestamp": "2026-02-03T10:30:00Z"
}
```

### OHLC Data

#### Get Candlestick Data
```http
GET /api/v1/forex/ohlc/{symbol}?timeframe=1h&limit=100
```

**Parameters:**
- `timeframe`: `1m`, `5m`, `15m`, `1h`, `4h`
- `limit`: 1-500 (default: 100)

### Charts

#### Get Candlestick Chart
```http
GET /api/v1/forex/chart/{symbol}?timeframe=1h&limit=50&show_ma=true&chart_type=candlestick
```

**Returns:** PNG image

**Parameters:**
- `timeframe`: `1m`, `5m`, `15m`, `1h`, `4h`
- `limit`: 10-200
- `show_ma`: true/false (show moving averages)
- `chart_type`: `candlestick` or `line`

#### Get Comparison Chart
```http
GET /api/v1/forex/chart/compare?symbols=eurusd,gbpusd,usdjpy&minutes=60
```

**Returns:** PNG image comparing multiple pairs (normalized %)

### Technical Analysis

#### Get Indicators
```http
GET /api/v1/forex/indicators/{symbol}?timeframe=1h
```

**Response:**
```json
{
  "symbol": "EURUSD",
  "timestamp": "2026-02-03T10:30:00Z",
  "sma_20": 1.08200,
  "sma_50": 1.08150,
  "sma_200": 1.07900,
  "ema_12": 1.08220,
  "ema_26": 1.08180,
  "rsi_14": 55.5,
  "macd": 0.00015,
  "macd_signal": 0.00012,
  "macd_histogram": 0.00003,
  "atr_14": 0.00085,
  "bollinger_upper": 1.08500,
  "bollinger_middle": 1.08200,
  "bollinger_lower": 1.07900,
  "adx": 25.5,
  "trend_direction": "bullish",
  "rsi_signal": "neutral"
}
```

### Alerts

#### Create Alert
```http
POST /api/v1/forex/alerts
```

**Body:**
```json
{
  "guild_id": 123456789,
  "user_id": 987654321,
  "channel_id": 111222333,
  "symbol": "xauusd",
  "condition": "above",
  "target_price": 2050.00
}
```

**Conditions:**
- `above` - triggers when price >= target
- `below` - triggers when price <= target
- `cross_up` - triggers when price crosses above target
- `cross_down` - triggers when price crosses below target

#### Get User Alerts
```http
GET /api/v1/forex/alerts/user/{user_id}
```

#### Delete Alert
```http
DELETE /api/v1/forex/alerts/{alert_id}
```

## WebSocket API

### Connection
```
ws://localhost:8000/ws/forex?client_id=bot-1&client_type=bot
```

### Client Messages

#### Subscribe to All Symbols
```json
{"type": "subscribe_all"}
```

#### Subscribe to Specific Symbols
```json
{"type": "subscribe", "symbols": ["eurusd", "gbpusd", "xauusd"]}
```

#### Unsubscribe
```json
{"type": "unsubscribe", "symbols": ["eurusd"]}
```

#### Get Price
```json
{"type": "get_price", "symbol": "eurusd"}
```

#### Ping
```json
{"type": "ping"}
```

### Server Messages

#### Snapshot (on connect)
```json
{
  "type": "snapshot",
  "data": {
    "eurusd": {"symbol": "EURUSD", "bid": 1.08234, ...},
    "gbpusd": {"symbol": "GBPUSD", "bid": 1.26543, ...}
  }
}
```

#### Price Update
```json
{
  "type": "price",
  "data": {
    "symbol": "EURUSD",
    "bid": 1.08235,
    "ask": 1.08238,
    "mid": 1.082365,
    "spread_pips": 0.3,
    "timestamp": "2026-02-03T10:30:01Z"
  }
}
```

#### Alert Triggered
```json
{
  "type": "alert_triggered",
  "data": {
    "alert_id": 1,
    "guild_id": 123456789,
    "user_id": 987654321,
    "channel_id": 111222333,
    "symbol": "XAUUSD",
    "condition": "above",
    "target_price": 2050.00,
    "triggered_price": 2050.15,
    "triggered_at": "2026-02-03T10:30:00Z"
  }
}
```

## Discord Bot Commands

### Price Commands (via Python Service)

| Command | Description |
|---------|-------------|
| `/fprice <symbol>` | Get live forex price |
| `/chart <symbol> [timeframe] [limit]` | Get candlestick chart |
| `/compare <symbol1> <symbol2> [symbol3] [symbol4]` | Compare multiple pairs |
| `/analysis <symbol> [timeframe]` | Get technical analysis |
| `/falert <symbol> <condition> <target>` | Create price alert |
| `/falerts` | List your active alerts |
| `/falertremove <id>` | Remove an alert |

### Legacy Commands (Direct Tiingo)

| Command | Description |
|---------|-------------|
| `/price <symbol>` | Get price (direct Tiingo) |
| `/alert <symbol> <condition> <target>` | Create alert (local) |
| `/alerts` | List alerts (local) |

## Available Symbols

The service supports all forex pairs available on Tiingo:

**Major Pairs:**
- EURUSD, GBPUSD, USDJPY, USDCHF, AUDUSD, USDCAD, NZDUSD

**Crosses:**
- EURGBP, EURJPY, GBPJPY, AUDJPY, CADJPY, etc.

**Metals:**
- XAUUSD (Gold), XAGUSD (Silver)

**Crypto (if enabled):**
- BTCUSD, ETHUSD

## Configuration

### Environment Variables

```env
# Enable forex service
FOREX_ENABLED=true

# Tiingo API key (required)
TIINGO_API_KEY=your_tiingo_api_key
```

### Discord Bot Configuration

```env
# Python Forex Service URL
FOREX_SERVICE_URL=http://localhost:8000

# Optional: Direct Tiingo connection (for fallback)
TIINGO_API_KEY=your_tiingo_api_key
```

## Running the Service

### Standalone
```bash
cd news-server
pip install -r requirements.txt
python -m app.main
```

### With Docker
```bash
docker-compose up -d news-api
```

## Performance Notes

- Price updates are streamed via WebSocket (low latency)
- OHLC data is aggregated in-memory from tick data
- Charts are generated on-demand (may take 1-2s for complex charts)
- Technical indicators require sufficient historical data
