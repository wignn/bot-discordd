package main

import (
	"context"
	"log/slog"
	"os"
	"os/signal"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/joho/godotenv"
	"github.com/wign/news-server/internal/api"
	"github.com/wign/news-server/internal/collector"
	"github.com/wign/news-server/internal/config"
	"github.com/wign/news-server/internal/database"
	"github.com/wign/news-server/internal/pipeline"
	"github.com/wign/news-server/internal/scraper"
	"github.com/wign/news-server/internal/ws"
)

func main() {
	_ = godotenv.Load()

	cfg := config.Load()

	level := slog.LevelInfo
	switch strings.ToUpper(cfg.LogLevel) {
	case "DEBUG":
		level = slog.LevelDebug
	case "WARN", "WARNING":
		level = slog.LevelWarn
	case "ERROR":
		level = slog.LevelError
	}

	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
		Level: level,
	}))
	slog.SetDefault(logger)

	slog.Info("news-server starting",
		"port", cfg.ServerPort,
		"rss_interval", cfg.RSSFetchSec,
		"stock_interval", cfg.StockFetchSec,
		"calendar_interval", cfg.CalendarCheckSec,
		"infoway_enabled", cfg.InfowayAPIKey != "",
	)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		sig := <-sigCh
		slog.Info("received signal, shutting down", "signal", sig)
		cancel()
	}()

	db, err := database.NewPool(ctx, cfg.DatabaseURL)
	if err != nil {
		slog.Error("database connection failed", "error", err)
		os.Exit(1)
	}
	defer db.Close()

	// WebSocket hub
	hub := ws.NewHub()
	go hub.Run()

	// HTTP/WebSocket server
	server := api.NewServer(hub, db, cfg.ServerPort, cfg.APIKeys)
	go func() {
		if err := server.Start(); err != nil {
			slog.Error("http server failed", "error", err)
			os.Exit(1)
		}
	}()

	// Collectors
	timeout := time.Duration(cfg.ScraperTimeout) * time.Second
	rssCollector := collector.NewRSSCollector(cfg.RSSMaxEntries, cfg.ScraperUA, timeout)
	stockCollector := collector.NewStockCollector(cfg.ScraperUA, timeout)
	calendarCollector := collector.NewCalendarCollector(timeout)
	articleScraper := scraper.NewArticleScraper(cfg.ScraperUA, timeout)

	newsPipeline := pipeline.NewNewsPipeline(rssCollector, articleScraper, db, hub)
	stockPipeline := pipeline.NewStockPipeline(stockCollector, db, hub)
	calendarPipeline := pipeline.NewCalendarPipeline(calendarCollector, hub)

	var infowayPipeline *pipeline.InfowayPipeline
	if cfg.InfowayAPIKey != "" {
		infowayPipeline = pipeline.NewInfowayPipeline(
			cfg.InfowayAPIKey,
			cfg.InfowayForexSymbols,
			cfg.InfowayCryptoSymbols,
			cfg.InfowayStockSymbols,
			hub,
		)
	}

	var wg sync.WaitGroup

	wg.Add(1)
	go func() {
		defer wg.Done()
		runScheduled(ctx, "news", time.Duration(cfg.RSSFetchSec)*time.Second, func() {
			newsPipeline.Run(ctx)
		})
	}()

	wg.Add(1)
	go func() {
		defer wg.Done()
		time.Sleep(5 * time.Second)
		runScheduled(ctx, "stock", time.Duration(cfg.StockFetchSec)*time.Second, func() {
			stockPipeline.Run(ctx)
		})
	}()

	wg.Add(1)
	go func() {
		defer wg.Done()
		time.Sleep(10 * time.Second)
		runScheduled(ctx, "calendar", time.Duration(cfg.CalendarCheckSec)*time.Second, func() {
			calendarPipeline.Run(ctx)
		})
	}()

	if infowayPipeline != nil {
		wg.Add(1)
		go func() {
			defer wg.Done()
			infowayPipeline.Run(ctx)
		}()
		slog.Info("infoway market data gateway enabled")

		// Volatility detector requires market data from infoway
		volatilityPipeline := pipeline.NewVolatilityPipeline(hub)
		wg.Add(1)
		go func() {
			defer wg.Done()
			// Wait for price cache to populate
			time.Sleep(30 * time.Second)
			volatilityPipeline.Run(ctx)
		}()
		slog.Info("gold volatility spike detector enabled")
	}

	slog.Info("news-server running", "port", cfg.ServerPort)
	wg.Wait()
	slog.Info("news-server stopped")
}

func runScheduled(ctx context.Context, name string, interval time.Duration, fn func()) {
	safeRun(name, fn)

	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			slog.Info("scheduler stopping", "pipeline", name)
			return
		case <-ticker.C:
			safeRun(name, fn)
		}
	}
}

func safeRun(name string, fn func()) {
	start := time.Now()

	defer func() {
		if r := recover(); r != nil {
			slog.Error("pipeline panic recovered",
				"pipeline", name,
				"panic", r,
			)
		}
	}()

	fn()

	elapsed := time.Since(start)
	slog.Debug("pipeline tick completed", "pipeline", name, "elapsed", elapsed)
}
