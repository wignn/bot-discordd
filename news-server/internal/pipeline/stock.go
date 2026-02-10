package pipeline

import (
	"context"
	"fmt"
	"log/slog"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/wign/news-server/internal/collector"
	"github.com/wign/news-server/internal/ws"
)

const maxStockNewsAgeHours = 2

type StockPipeline struct {
	collector *collector.StockCollector
	db        *pgxpool.Pool
	hub       *ws.Hub
}

func NewStockPipeline(
	sc *collector.StockCollector,
	db *pgxpool.Pool,
	hub *ws.Hub,
) *StockPipeline {
	return &StockPipeline{
		collector: sc,
		db:        db,
		hub:       hub,
	}
}

func (p *StockPipeline) Run(ctx context.Context) {
	slog.Info("stock pipeline: starting")

	entries := p.collector.FetchLatest(ctx, 30)
	slog.Info("stock pipeline: entries fetched", "count", len(entries))

	processed := 0
	skipped := 0

	for _, entry := range entries {
		result := p.processEntry(ctx, entry)
		if result == "processed" {
			processed++
		} else {
			skipped++
		}
	}

	slog.Info("stock pipeline: completed", "processed", processed, "skipped", skipped)
}

func (p *StockPipeline) processEntry(ctx context.Context, entry collector.StockNewsEntry) string {
	if entry.PublishedAt != nil {
		cutoff := time.Now().UTC().Add(-maxStockNewsAgeHours * time.Hour)
		if entry.PublishedAt.Before(cutoff) {
			return "too_old"
		}
	}

	var exists bool
	err := p.db.QueryRow(ctx,
		"SELECT EXISTS(SELECT 1 FROM stock_news WHERE content_hash = $1)",
		entry.ContentHash,
	).Scan(&exists)
	if err != nil {
		slog.Warn("stock dedup check failed", "error", err)
	} else if exists {
		return "duplicate"
	}

	impactLevel := "low"
	if len(entry.Tickers) >= 3 {
		impactLevel = "high"
	} else if len(entry.Tickers) >= 1 {
		impactLevel = "medium"
	}

	publishedAt := ""
	if entry.PublishedAt != nil {
		publishedAt = entry.PublishedAt.Format(time.RFC3339)
	}

	tickersStr := strings.Join(entry.Tickers, ",")
	_, err = p.db.Exec(ctx,
		`INSERT INTO stock_news 
			(content_hash, original_url, title, source_name, category, 
			 tickers, sentiment, impact_level, is_processed, processed_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, TRUE, NOW())
		 ON CONFLICT (content_hash) DO NOTHING`,
		entry.ContentHash, entry.Link, entry.Title, entry.SourceName,
		entry.Category, tickersStr, "neutral", impactLevel,
	)
	if err != nil {
		slog.Warn("stock db insert failed", "error", err)
	}

	// Broadcast directly via WebSocket hub
	stockData := ws.StockNewsData{
		ID:          entry.ContentHash,
		Title:       entry.Title,
		Summary:     truncateStr(entry.Content, 1000),
		SourceName:  entry.SourceName,
		SourceURL:   entry.Link,
		URL:         entry.Link,
		Category:    entry.Category,
		Tickers:     entry.Tickers,
		Sentiment:   "neutral",
		ImpactLevel: impactLevel,
		PublishedAt: publishedAt,
		ProcessedAt: time.Now().UTC().Format(time.RFC3339),
	}

	embed := ws.BuildStockEmbed(stockData)
	count := p.hub.Broadcast(ws.EventStockNewsNew, map[string]interface{}{
		"article":       stockData,
		"discord_embed": embed,
		"asset_type":    "stock",
	}, "stock_news")

	slog.Info("stock broadcast ok",
		"clients", count,
		"title", truncateStr(entry.Title, 50),
		"tickers", entry.Tickers,
	)

	return "processed"
}

var _ = fmt.Sprintf // suppress unused import
