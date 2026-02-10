package pipeline

import (
	"context"
	"crypto/sha256"
	"fmt"
	"log/slog"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/wign/news-server/internal/collector"
	"github.com/wign/news-server/internal/htmlutil"
	"github.com/wign/news-server/internal/scraper"
	"github.com/wign/news-server/internal/ws"
)

const maxNewsAgeHours = 2

type NewsPipeline struct {
	rss     *collector.RSSCollector
	scraper *scraper.ArticleScraper
	db      *pgxpool.Pool
	hub     *ws.Hub
}

func NewNewsPipeline(
	rss *collector.RSSCollector,
	sc *scraper.ArticleScraper,
	db *pgxpool.Pool,
	hub *ws.Hub,
) *NewsPipeline {
	return &NewsPipeline{
		rss:     rss,
		scraper: sc,
		db:      db,
		hub:     hub,
	}
}

func (p *NewsPipeline) Run(ctx context.Context) {
	slog.Info("news pipeline: starting")

	results := p.rss.FetchAllFeeds(ctx, collector.DefaultForexFeeds)

	totalEntries := 0
	for _, entries := range results {
		totalEntries += len(entries)
	}
	slog.Info("news pipeline: feeds fetched", "feeds", len(results), "total_entries", totalEntries)

	processed := 0
	skipped := 0

	for feedURL, entries := range results {
		sourceName := collector.FeedNameByURL(feedURL)

		for _, entry := range entries {
			result := p.processEntry(ctx, entry, feedURL, sourceName)
			if result == "processed" {
				processed++
			} else {
				skipped++
			}
		}
	}

	slog.Info("news pipeline: completed", "processed", processed, "skipped", skipped)
}

func (p *NewsPipeline) processEntry(ctx context.Context, entry collector.RSSEntry, feedURL, sourceName string) string {
	if entry.PublishedAt != nil {
		cutoff := time.Now().UTC().Add(-maxNewsAgeHours * time.Hour)
		if entry.PublishedAt.Before(cutoff) {
			return "too_old"
		}
	}

	hash := entry.ContentHash
	var exists bool
	err := p.db.QueryRow(ctx,
		"SELECT EXISTS(SELECT 1 FROM news_articles WHERE content_hash = $1)",
		hash,
	).Scan(&exists)
	if err != nil {
		slog.Warn("dedup check failed, processing anyway", "error", err)
	} else if exists {
		return "duplicate"
	}

	title := entry.Title
	content := htmlutil.StripTags(entry.Content)
	description := content
	var imageURL string
	publishedAt := ""
	if entry.PublishedAt != nil {
		publishedAt = entry.PublishedAt.Format(time.RFC3339)
	}

	if len(content) < 200 && entry.Link != "" {
		article, err := p.scraper.Scrape(ctx, entry.Link)
		if err != nil {
			slog.Debug("scrape failed, using rss fallback", "url", entry.Link, "error", err)
		} else if article != nil {
			content = article.Content
			if article.ImageURL != "" {
				imageURL = article.ImageURL
			}
			if article.PublishedAt != "" && publishedAt == "" {
				publishedAt = article.PublishedAt
			}
		}
	}

	summary := htmlutil.ExtractSummary(description, 500)
	if summary == "" {
		summary = htmlutil.ExtractSummary(content, 500)
	}

	sourceID := p.ensureSource(ctx)

	_, err = p.db.Exec(ctx,
		`INSERT INTO news_articles 
			(id, source_id, content_hash, original_url, original_title, original_content, 
			 translated_title, summary, is_processed, processed_at, published_at)
		 VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, '', $6, TRUE, NOW(), $7)
		 ON CONFLICT (content_hash) DO NOTHING`,
		sourceID, hash, entry.Link, title,
		truncateStr(content, 5000), summary,
		nilIfEmpty(publishedAt),
	)
	if err != nil {
		slog.Warn("db insert failed", "error", err, "url", entry.Link)
	} else {
		slog.Info("article saved", "title", truncateStr(title, 50))
	}

	// Broadcast directly via WebSocket hub
	articleData := ws.NewsArticleData{
		ID:          hash,
		Title:       title,
		SourceName:  sourceName,
		SourceURL:   feedURL,
		URL:         entry.Link,
		Summary:     summary,
		ImpactLevel: "medium",
		PublishedAt: publishedAt,
		ProcessedAt: time.Now().UTC().Format(time.RFC3339),
		ImageURL:    imageURL,
	}

	embed := ws.BuildNewsEmbed(articleData)
	count := p.hub.Broadcast(ws.EventNewsNew, map[string]interface{}{
		"article":       articleData,
		"discord_embed": embed,
	}, "news")

	slog.Info("broadcast ok", "clients", count, "title", truncateStr(title, 50))

	return "processed"
}

func (p *NewsPipeline) ensureSource(ctx context.Context) string {
	var id string
	err := p.db.QueryRow(ctx,
		"SELECT id FROM news_sources WHERE slug = 'default' LIMIT 1",
	).Scan(&id)

	if err == nil {
		return id
	}

	// Generate a deterministic UUID from the hash (format: 8-4-4-4-12)
	hash := fmt.Sprintf("%x", sha256.Sum256([]byte("default-source")))
	newID := fmt.Sprintf("%s-%s-%s-%s-%s", hash[0:8], hash[8:12], hash[12:16], hash[16:20], hash[20:32])
	_, err = p.db.Exec(ctx,
		`INSERT INTO news_sources (id, name, slug, source_type, url, is_active)
		 VALUES ($1, 'Default Source', 'default', 'rss', 'https://example.com', TRUE)
		 ON CONFLICT (slug) DO NOTHING`,
		newID,
	)
	if err != nil {
		slog.Warn("create default source failed", "error", err)
	}

	return newID
}

func truncateStr(s string, maxLen int) string {
	if len(s) > maxLen {
		return s[:maxLen]
	}
	return s
}

func nilIfEmpty(s string) *string {
	if s == "" {
		return nil
	}
	return &s
}
