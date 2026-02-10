package collector

import (
	"context"
	"crypto/sha256"
	"fmt"
	"log/slog"
	"net/http"
	"strings"
	"sync"
	"time"

	"github.com/mmcdole/gofeed"
)

type RSSEntry struct {
	Title       string
	Link        string
	Content     string
	PublishedAt *time.Time
	Author      string
	Tags        []string
	ContentHash string
	SourceName  string
}

func ComputeContentHash(url, title string) string {
	h := sha256.Sum256([]byte(url + "|" + title))
	return fmt.Sprintf("%x", h)
}

type FeedSource struct {
	Name     string
	URL      string
	RSSURL   string
	Category string
}

var DefaultForexFeeds = []FeedSource{
	{Name: "Thomson Reuters", URL: "https://ir.thomsonreuters.com", RSSURL: "https://ir.thomsonreuters.com/rss/news-releases.xml?items=15", Category: "general"},
	{Name: "Reuters - Markets", URL: "https://www.reuters.com/markets", RSSURL: "https://www.rssboard.org/files/sample-rss-2.xml", Category: "general"},
	{Name: "InvestingLive", URL: "https://investinglive.com", RSSURL: "https://investinglive.com/feed/news/", Category: "forex"},
	{Name: "FXStreet", URL: "https://www.fxstreet-id.com", RSSURL: "https://www.fxstreet-id.com/rss/news", Category: "forex"},
	{Name: "Investing.com - Forex News", URL: "https://id.investing.com/news/forex-news", RSSURL: "https://id.investing.com/rss/news_301.rss", Category: "forex"},
	{Name: "Investing.com - Economic Indicators", URL: "https://id.investing.com/news/economic-indicators", RSSURL: "https://id.investing.com/rss/news_95.rss", Category: "economic"},
	{Name: "Federal Reserve", URL: "https://www.federalreserve.gov", RSSURL: "https://www.federalreserve.gov/feeds/press_all.xml", Category: "central_bank"},
	{Name: "ECB", URL: "https://www.ecb.europa.eu", RSSURL: "https://www.ecb.europa.eu/rss/press.html", Category: "central_bank"},
}

type RSSCollector struct {
	parser     *gofeed.Parser
	maxEntries int
	semaphore  chan struct{}
	userAgent  string
	timeout    time.Duration
}

func NewRSSCollector(maxEntries int, userAgent string, timeout time.Duration) *RSSCollector {
	p := gofeed.NewParser()
	p.Client = &http.Client{
		Timeout: timeout,
		Transport: &http.Transport{
			MaxIdleConns:        20,
			MaxIdleConnsPerHost: 5,
			IdleConnTimeout:     30 * time.Second,
		},
	}
	p.UserAgent = userAgent

	return &RSSCollector{
		parser:     p,
		maxEntries: maxEntries,
		semaphore:  make(chan struct{}, 6), // max 6 concurrent
		userAgent:  userAgent,
		timeout:    timeout,
	}
}

func (c *RSSCollector) FetchFeed(ctx context.Context, source FeedSource) []RSSEntry {
	ctx, cancel := context.WithTimeout(ctx, c.timeout)
	defer cancel()

	feed, err := c.parser.ParseURLWithContext(source.RSSURL, ctx)
	if err != nil {
		slog.Error("fetch feed failed", "source", source.Name, "url", source.RSSURL, "error", err)
		return nil
	}

	limit := c.maxEntries
	if len(feed.Items) < limit {
		limit = len(feed.Items)
	}

	var entries []RSSEntry
	for _, item := range feed.Items[:limit] {
		entry := c.parseItem(item, source.Name)
		if entry != nil {
			entries = append(entries, *entry)
		}
	}

	slog.Info("feed fetched", "source", source.Name, "entries", len(entries))
	return entries
}

func (c *RSSCollector) FetchAllFeeds(ctx context.Context, feeds []FeedSource) map[string][]RSSEntry {
	var mu sync.Mutex
	results := make(map[string][]RSSEntry)

	var wg sync.WaitGroup
	for _, feed := range feeds {
		wg.Add(1)
		go func(f FeedSource) {
			defer wg.Done()

			// Acquire semaphore
			c.semaphore <- struct{}{}
			defer func() { <-c.semaphore }()

			entries := c.FetchFeed(ctx, f)

			mu.Lock()
			results[f.RSSURL] = entries
			mu.Unlock()

			// Small delay between feeds to be polite
			time.Sleep(100 * time.Millisecond)
		}(feed)
	}

	wg.Wait()
	return results
}

func (c *RSSCollector) parseItem(item *gofeed.Item, sourceName string) *RSSEntry {
	title := strings.TrimSpace(item.Title)
	link := strings.TrimSpace(item.Link)

	if title == "" || link == "" {
		return nil
	}

	content := ""
	if item.Content != "" {
		content = item.Content
	} else if item.Description != "" {
		content = item.Description
	}

	var publishedAt *time.Time
	if item.PublishedParsed != nil {
		publishedAt = item.PublishedParsed
	} else if item.UpdatedParsed != nil {
		publishedAt = item.UpdatedParsed
	}

	author := ""
	if item.Author != nil {
		author = item.Author.Name
	}

	var tags []string
	for _, cat := range item.Categories {
		cat = strings.TrimSpace(cat)
		if cat != "" {
			tags = append(tags, cat)
		}
	}

	hash := ComputeContentHash(link, title)

	return &RSSEntry{
		Title:       title,
		Link:        link,
		Content:     content,
		PublishedAt: publishedAt,
		Author:      author,
		Tags:        tags,
		ContentHash: hash,
		SourceName:  sourceName,
	}
}

func FeedNameByURL(rssURL string) string {
	for _, f := range DefaultForexFeeds {
		if f.RSSURL == rssURL {
			return f.Name
		}
	}

	lower := strings.ToLower(rssURL)
	switch {
	case strings.Contains(lower, "fxstreet"):
		return "FXStreet"
	case strings.Contains(lower, "investing.com"):
		return "Investing.com"
	case strings.Contains(lower, "reuters"):
		return "Reuters"
	case strings.Contains(lower, "federalreserve"):
		return "Federal Reserve"
	case strings.Contains(lower, "ecb.europa"):
		return "ECB"
	default:
		return "Unknown"
	}
}
