package collector

import (
	"context"
	"crypto/md5"
	"fmt"
	"log/slog"
	"net/http"
	"regexp"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/mmcdole/gofeed"
)

type StockNewsEntry struct {
	Title       string
	Link        string
	Content     string
	PublishedAt *time.Time
	Author      string
	Tags        []string
	ContentHash string
	SourceName  string
	Category    string
	Tickers     []string
}

var IndonesiaStockFeeds = []FeedSource{
	{Name: "CNBC Indonesia - Market", URL: "https://www.cnbcindonesia.com/market", RSSURL: "https://www.cnbcindonesia.com/market/rss", Category: "market"},
	{Name: "Investing.com Indonesia - Market", URL: "https://id.investing.com", RSSURL: "https://id.investing.com/rss/news_25.rss", Category: "market"},
	{Name: "Tempo.co - Market", URL: "https://www.tempo.co", RSSURL: "https://rss.tempo.co/bisnis", Category: "market"},
	{Name: "Detik - Market", URL: "https://finance.detik.com", RSSURL: "https://finance.detik.com/rss", Category: "market"},
	{Name: "CNN - Market", URL: "https://www.cnnindonesia.com/ekonomi", RSSURL: "https://www.cnnindonesia.com/ekonomi/rss", Category: "market"},
}

var stockKeywords = map[string]struct{}{
	"ihsg": {}, "idx": {}, "bei": {}, "bursa efek": {}, "saham": {}, "emiten": {}, "dividen": {},
	"ipo": {}, "right issue": {}, "stock split": {}, "buyback": {}, "tender offer": {},
	"listing": {}, "delisting": {}, "suspensi": {}, "trading halt": {},
	"naik": {}, "turun": {}, "melemah": {}, "menguat": {}, "bullish": {}, "bearish": {},
	"koreksi": {}, "rally": {}, "rebound": {}, "profit taking": {}, "window dressing": {},
	"laba": {}, "rugi": {}, "pendapatan": {}, "omzet": {}, "revenue": {}, "net profit": {},
	"laporan keuangan": {}, "kuartal": {}, "semester": {}, "tahunan": {},
	"eps": {}, "per": {}, "pbv": {}, "roe": {}, "roa": {}, "der": {},
	"akuisisi": {}, "merger": {}, "divestasi": {}, "spin off": {}, "rights issue": {},
	"obligasi": {}, "sukuk": {}, "private placement": {},
	"perbankan": {}, "bank": {}, "properti": {}, "konstruksi": {}, "tambang": {}, "mining": {},
	"energi": {}, "telekomunikasi": {}, "consumer": {}, "fmcg": {}, "farmasi": {},
	"otomotif": {}, "infrastruktur": {}, "bumn": {},
	"bbca": {}, "bbri": {}, "bmri": {}, "bbni": {}, "tlkm": {}, "asii": {}, "unvr": {}, "hmsp": {},
	"ggrm": {}, "icbp": {}, "indf": {}, "klbf": {}, "pgas": {}, "ptba": {}, "adro": {}, "antm": {},
	"inco": {}, "mdka": {}, "goto": {}, "buka": {}, "arto": {}, "bris": {},
}

var knownTickers = map[string]struct{}{
	"BBCA": {}, "BBRI": {}, "BMRI": {}, "BBNI": {}, "TLKM": {}, "ASII": {}, "UNVR": {}, "HMSP": {},
	"GGRM": {}, "ICBP": {}, "INDF": {}, "KLBF": {}, "PGAS": {}, "PTBA": {}, "ADRO": {}, "ANTM": {},
	"INCO": {}, "MDKA": {}, "GOTO": {}, "BUKA": {}, "ARTO": {}, "BRIS": {}, "BBTN": {}, "SMGR": {},
	"INTP": {}, "EXCL": {}, "ISAT": {}, "TOWR": {}, "TBIG": {}, "MNCN": {}, "SCMA": {}, "AKRA": {},
	"UNTR": {}, "MEDC": {}, "ESSA": {}, "ACES": {}, "MAPI": {}, "ERAA": {}, "SIDO": {}, "KAEF": {},
	"CPIN": {}, "JPFA": {}, "MAIN": {}, "SRIL": {}, "TKIM": {}, "INKP": {}, "BRPT": {}, "TPIA": {},
	"AMRT": {}, "MIDI": {}, "LPPF": {}, "MYOR": {}, "ROTI": {}, "ULTJ": {}, "MLBI": {}, "DLTA": {},
	"IHSG": {}, "JKSE": {},
}

var tickerPattern = regexp.MustCompile(`\b([A-Z]{4})\b`)

type StockCollector struct {
	parser    *gofeed.Parser
	semaphore chan struct{}
	timeout   time.Duration
}

func NewStockCollector(userAgent string, timeout time.Duration) *StockCollector {
	p := gofeed.NewParser()
	p.Client = &http.Client{
		Timeout: timeout,
		Transport: &http.Transport{
			MaxIdleConns:        10,
			MaxIdleConnsPerHost: 3,
			IdleConnTimeout:     30 * time.Second,
		},
	}
	p.UserAgent = userAgent

	return &StockCollector{
		parser:    p,
		semaphore: make(chan struct{}, 6),
		timeout:   timeout,
	}
}

func (c *StockCollector) FetchLatest(ctx context.Context, maxEntries int) []StockNewsEntry {
	results := c.fetchAllFeeds(ctx)

	var allEntries []StockNewsEntry
	for _, entries := range results {
		allEntries = append(allEntries, entries...)
	}

	sort.Slice(allEntries, func(i, j int) bool {
		if allEntries[i].PublishedAt == nil {
			return false
		}
		if allEntries[j].PublishedAt == nil {
			return true
		}
		return allEntries[i].PublishedAt.After(*allEntries[j].PublishedAt)
	})

	seen := make(map[string]struct{})
	var unique []StockNewsEntry
	for _, entry := range allEntries {
		if _, exists := seen[entry.ContentHash]; !exists {
			seen[entry.ContentHash] = struct{}{}
			unique = append(unique, entry)
		}
	}

	if len(unique) > maxEntries {
		unique = unique[:maxEntries]
	}

	return unique
}

func (c *StockCollector) fetchAllFeeds(ctx context.Context) map[string][]StockNewsEntry {
	var mu sync.Mutex
	results := make(map[string][]StockNewsEntry)

	var wg sync.WaitGroup
	for _, feed := range IndonesiaStockFeeds {
		wg.Add(1)
		go func(f FeedSource) {
			defer wg.Done()

			c.semaphore <- struct{}{}
			defer func() { <-c.semaphore }()

			entries := c.fetchFeed(ctx, f)

			mu.Lock()
			results[f.Name] = entries
			mu.Unlock()

			time.Sleep(100 * time.Millisecond)
		}(feed)
	}

	wg.Wait()
	return results
}

func (c *StockCollector) fetchFeed(ctx context.Context, source FeedSource) []StockNewsEntry {
	ctx, cancel := context.WithTimeout(ctx, c.timeout)
	defer cancel()

	feed, err := c.parser.ParseURLWithContext(source.RSSURL, ctx)
	if err != nil {
		slog.Error("stock feed fetch failed", "source", source.Name, "error", err)
		return nil
	}

	limit := 20
	if len(feed.Items) < limit {
		limit = len(feed.Items)
	}

	var entries []StockNewsEntry
	for _, item := range feed.Items[:limit] {
		entry := c.parseItem(item, source)
		if entry != nil && isRelevantStock(entry) {
			entries = append(entries, *entry)
		}
	}

	slog.Info("stock feed fetched", "source", source.Name, "entries", len(entries))
	return entries
}

func (c *StockCollector) parseItem(item *gofeed.Item, source FeedSource) *StockNewsEntry {
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

	reHTML := regexp.MustCompile(`<[^>]+>`)
	content = reHTML.ReplaceAllString(content, "")
	content = strings.TrimSpace(content)
	if len(content) > 2000 {
		content = content[:2000]
	}

	var publishedAt *time.Time
	if item.PublishedParsed != nil {
		publishedAt = item.PublishedParsed
	} else if item.UpdatedParsed != nil {
		publishedAt = item.UpdatedParsed
	}

	var tags []string
	for _, cat := range item.Categories {
		cat = strings.TrimSpace(cat)
		if cat != "" {
			tags = append(tags, cat)
		}
	}

	hashContent := title + link
	hash := fmt.Sprintf("%x", md5.Sum([]byte(hashContent)))

	tickers := extractTickers(title + " " + content)

	author := ""
	if item.Author != nil {
		author = item.Author.Name
	}

	return &StockNewsEntry{
		Title:       title,
		Link:        link,
		Content:     content,
		PublishedAt: publishedAt,
		Author:      author,
		Tags:        tags,
		ContentHash: hash,
		SourceName:  source.Name,
		Category:    source.Category,
		Tickers:     tickers,
	}
}

func isRelevantStock(entry *StockNewsEntry) bool {
	if len(entry.Tickers) > 0 {
		return true
	}

	text := strings.ToLower(entry.Title + " " + entry.Content)
	words := strings.Fields(text)
	wordSet := make(map[string]struct{}, len(words))
	for _, w := range words {
		wordSet[w] = struct{}{}
	}

	for kw := range stockKeywords {
		if !strings.Contains(kw, " ") {
			if _, found := wordSet[kw]; found {
				return true
			}
		}
	}

	for kw := range stockKeywords {
		if strings.Contains(kw, " ") && strings.Contains(text, kw) {
			return true
		}
	}

	return false
}

func extractTickers(text string) []string {
	upper := strings.ToUpper(text)
	matches := tickerPattern.FindAllString(upper, -1)

	seen := make(map[string]struct{})
	var valid []string
	for _, m := range matches {
		if _, ok := knownTickers[m]; ok {
			if _, dup := seen[m]; !dup {
				seen[m] = struct{}{}
				valid = append(valid, m)
			}
		}
	}

	return valid
}
