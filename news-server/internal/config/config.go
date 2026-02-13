package config

import (
	"os"
	"strconv"
	"strings"
)

type Config struct {
	DatabaseURL      string
	ServerPort       int
	APIKeys          string
	ScraperTimeout   int
	ScraperUA        string
	RSSMaxEntries    int
	RSSFetchSec      int
	StockFetchSec    int
	CalendarCheckSec int
	LogLevel         string

	InfowayAPIKey        string
	InfowayForexSymbols  string
	InfowayCryptoSymbols string
}

func Load() *Config {
	cfg := &Config{
		DatabaseURL:      getEnv("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/forex"),
		ServerPort:       getEnvInt("PORT", 8000),
		APIKeys:          getEnv("API_KEYS", ""),
		ScraperTimeout:   getEnvInt("SCRAPER_TIMEOUT", 30),
		ScraperUA:        getEnv("SCRAPER_USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"),
		RSSMaxEntries:    getEnvInt("RSS_MAX_ENTRIES_PER_FEED", 50),
		RSSFetchSec:      getEnvInt("RSS_FETCH_SEC", 20),
		StockFetchSec:    getEnvInt("STOCK_FETCH_SEC", 20),
		CalendarCheckSec: getEnvInt("CALENDAR_CHECK_SEC", 60),
		LogLevel:         getEnv("LOG_LEVEL", "INFO"),

		InfowayAPIKey:        getEnv("INFOWAY_API_KEY", ""),
		InfowayForexSymbols:  getEnv("INFOWAY_FOREX_SYMBOLS", "EURUSD,GBPUSD,USDJPY,XAUUSD"),
		InfowayCryptoSymbols: getEnv("INFOWAY_CRYPTO_SYMBOLS", "BTCUSDT,ETHUSDT"),
	}

	cfg.DatabaseURL = strings.Replace(cfg.DatabaseURL, "postgresql+asyncpg://", "postgres://", 1)
	cfg.DatabaseURL = strings.Replace(cfg.DatabaseURL, "postgresql://", "postgres://", 1)

	return cfg
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func getEnvInt(key string, fallback int) int {
	if v := os.Getenv(key); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			return n
		}
	}
	return fallback
}
