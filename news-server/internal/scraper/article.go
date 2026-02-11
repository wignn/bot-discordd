package scraper

import (
	"context"
	"fmt"
	"log/slog"
	"net/http"
	"net/url"
	"regexp"
	"strings"
	"time"

	"github.com/PuerkitoBio/goquery"

	"github.com/wign/news-server/internal/htmlutil"
)

type ScrapedArticle struct {
	URL         string
	Title       string
	Content     string
	Author      string
	PublishedAt string
	ImageURL    string
	Tags        []string
	WordCount   int
}

type ArticleScraper struct {
	client *http.Client
}

func NewArticleScraper(userAgent string, timeout time.Duration) *ArticleScraper {
	return &ArticleScraper{
		client: &http.Client{
			Timeout: timeout,
			Transport: &http.Transport{
				MaxIdleConns:        10,
				MaxIdleConnsPerHost: 3,
				IdleConnTimeout:     30 * time.Second,
			},
			CheckRedirect: func(req *http.Request, via []*http.Request) error {
				if len(via) >= 5 {
					return fmt.Errorf("too many redirects")
				}
				return nil
			},
		},
	}
}

func (s *ArticleScraper) Scrape(ctx context.Context, articleURL string) (*ScrapedArticle, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, articleURL, nil)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
	req.Header.Set("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
	req.Header.Set("Accept-Language", "en-US,en;q=0.5")

	resp, err := s.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("fetch page: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("page returned %d", resp.StatusCode)
	}

	doc, err := goquery.NewDocumentFromReader(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("parse html: %w", err)
	}

	doc.Find("script, style, nav, header, footer, aside, .ad, .advertisement, .social-share").Remove()

	title := extractTitle(doc)
	content := extractContent(doc)

	if title == "" || content == "" {
		return nil, fmt.Errorf("could not extract title or content")
	}

	content = htmlutil.CleanContent(content)

	return &ScrapedArticle{
		URL:         articleURL,
		Title:       title,
		Content:     content,
		Author:      extractAuthor(doc),
		PublishedAt: extractDate(doc),
		ImageURL:    extractImage(doc, articleURL),
		Tags:        extractTags(doc),
		WordCount:   len(strings.Fields(content)),
	}, nil
}

func extractTitle(doc *goquery.Document) string {
	selectors := []string{
		"article h1",
		"h1.article-title",
		"h1.entry-title",
		"h1.post-title",
		".article-header h1",
		"h1[itemprop='headline']",
	}

	for _, sel := range selectors {
		if text := strings.TrimSpace(doc.Find(sel).First().Text()); text != "" {
			return text
		}
	}

	if content, exists := doc.Find("meta[property='og:title']").First().Attr("content"); exists {
		return strings.TrimSpace(content)
	}

	return strings.TrimSpace(doc.Find("title").First().Text())
}

func extractContent(doc *goquery.Document) string {
	selectors := []string{
		"article .content",
		"article .entry-content",
		"article .post-content",
		"article .article-body",
		".article-content",
		".story-body",
		"[itemprop='articleBody']",
	}

	for _, sel := range selectors {
		node := doc.Find(sel).First()
		if node.Length() > 0 {
			text := strings.TrimSpace(node.Text())
			if len(text) > 200 {
				return text
			}
		}
	}

	var paragraphs []string
	doc.Find("article p").Each(func(_ int, s *goquery.Selection) {
		text := strings.TrimSpace(s.Text())
		if text != "" {
			paragraphs = append(paragraphs, text)
		}
	})
	if joined := strings.Join(paragraphs, "\n\n"); len(joined) > 200 {
		return joined
	}

	var longParagraphs []string
	doc.Find("p").Each(func(_ int, s *goquery.Selection) {
		text := strings.TrimSpace(s.Text())
		if len(text) > 50 {
			longParagraphs = append(longParagraphs, text)
		}
	})

	return strings.Join(longParagraphs, "\n\n")
}

func extractAuthor(doc *goquery.Document) string {
	selectors := []string{
		"[rel='author']",
		".author-name",
		".byline",
		"[itemprop='author']",
	}

	for _, sel := range selectors {
		if text := strings.TrimSpace(doc.Find(sel).First().Text()); text != "" {
			return text
		}
	}

	if content, exists := doc.Find("meta[name='author']").First().Attr("content"); exists {
		return strings.TrimSpace(content)
	}

	return ""
}

func extractDate(doc *goquery.Document) string {
	// Datetime attribute
	if dt, exists := doc.Find("time[datetime]").First().Attr("datetime"); exists {
		return dt
	}
	if dt, exists := doc.Find("[itemprop='datePublished']").First().Attr("datetime"); exists {
		return dt
	}
	if content, exists := doc.Find("[itemprop='datePublished']").First().Attr("content"); exists {
		return content
	}
	if content, exists := doc.Find("meta[property='article:published_time']").First().Attr("content"); exists {
		return content
	}

	return ""
}

func extractImage(doc *goquery.Document, baseURL string) string {
	// Try og:image first
	if content, exists := doc.Find("meta[property='og:image']").First().Attr("content"); exists {
		return resolveURL(baseURL, content)
	}

	selectors := []string{
		"article img",
		".article-image img",
		".featured-image img",
	}

	for _, sel := range selectors {
		if src, exists := doc.Find(sel).First().Attr("src"); exists && src != "" {
			return resolveURL(baseURL, src)
		}
	}

	return ""
}

func extractTags(doc *goquery.Document) []string {
	seen := make(map[string]struct{})
	var tags []string

	// Meta keywords
	if content, exists := doc.Find("meta[name='keywords']").First().Attr("content"); exists {
		for _, k := range strings.Split(content, ",") {
			k = strings.TrimSpace(k)
			if k != "" {
				if _, dup := seen[k]; !dup {
					seen[k] = struct{}{}
					tags = append(tags, k)
				}
			}
		}
	}

	// Tag links
	doc.Find(".tags a, .post-tags a, [rel='tag']").Each(func(_ int, s *goquery.Selection) {
		text := strings.TrimSpace(s.Text())
		if text != "" {
			if _, dup := seen[text]; !dup {
				seen[text] = struct{}{}
				tags = append(tags, text)
			}
		}
	})

	if len(tags) > 10 {
		tags = tags[:10]
	}

	return tags
}

func resolveURL(base, ref string) string {
	if strings.HasPrefix(ref, "http://") || strings.HasPrefix(ref, "https://") {
		return ref
	}
	baseU, err := url.Parse(base)
	if err != nil {
		return ref
	}
	refU, err := url.Parse(ref)
	if err != nil {
		return ref
	}
	return baseU.ResolveReference(refU).String()
}

var _ = regexp.MustCompile
var _ = slog.Info
