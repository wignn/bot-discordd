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
	client    *http.Client
	userAgent string
}

func NewArticleScraper(userAgent string, timeout time.Duration) *ArticleScraper {
	if userAgent == "" {
		userAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
	}
	return &ArticleScraper{
		userAgent: userAgent,
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
	
	// Set comprehensive headers to appear as a real browser
	req.Header.Set("User-Agent", s.userAgent)
	req.Header.Set("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8")
	req.Header.Set("Accept-Language", "en-US,en;q=0.9")
	req.Header.Set("Accept-Encoding", "gzip, deflate, br")
	req.Header.Set("DNT", "1")
	req.Header.Set("Connection", "keep-alive")
	req.Header.Set("Upgrade-Insecure-Requests", "1")
	req.Header.Set("Sec-Fetch-Dest", "document")
	req.Header.Set("Sec-Fetch-Mode", "navigate")
	req.Header.Set("Sec-Fetch-Site", "none")
	req.Header.Set("Sec-Fetch-User", "?1")
	req.Header.Set("Cache-Control", "max-age=0")
	
	parsedURL, _ := url.Parse(articleURL)
	if parsedURL != nil && parsedURL.Host != "" {
		req.Header.Set("Referer", fmt.Sprintf("%s://%s/", parsedURL.Scheme, parsedURL.Host))
	}

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

	logPageStructure(doc)

	doc.Find("script, style, nav, header, footer, aside, .ad, .advertisement, .social-share").Remove()

	title := extractTitle(doc)
	content := extractContent(doc)

	if title == "" {
		slog.Warn("failed to extract title", "url", articleURL)
	}
	if content == "" {
		slog.Warn("failed to extract content", "url", articleURL)
	}

	if title == "" || content == "" {
		return nil, fmt.Errorf("could not extract title or content (title=%t, content=%t)", title != "", content != "")
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

func logPageStructure(doc *goquery.Document) {
	doc.Find("h1").Each(func(i int, s *goquery.Selection) {
		class := s.AttrOr("class", "")
		id := s.AttrOr("id", "")
		text := strings.TrimSpace(s.Text())
		if len(text) > 100 {
			text = text[:100] + "..."
		}
		slog.Debug("found h1", "index", i, "class", class, "id", id, "text", text)
	})

	doc.Find("article, main").Each(func(i int, s *goquery.Selection) {
		tag := goquery.NodeName(s)
		class := s.AttrOr("class", "")
		id := s.AttrOr("id", "")
		pCount := s.Find("p").Length()
		slog.Debug("found content container", "tag", tag, "class", class, "id", id, "paragraphs", pCount)
	})

	if ogTitle, exists := doc.Find("meta[property='og:title']").Attr("content"); exists {
		slog.Debug("found og:title", "content", ogTitle)
	}
}

func extractTitle(doc *goquery.Document) string {
	if content, exists := doc.Find("meta[property='og:title']").First().Attr("content"); exists && content != "" {
		return strings.TrimSpace(content)
	}
	if content, exists := doc.Find("meta[name='twitter:title']").First().Attr("content"); exists && content != "" {
		return strings.TrimSpace(content)
	}

	selectors := []string{
		"article h1",
		"h1.article-title",
		"h1.entry-title",
		"h1.post-title",
		".article-header h1",
		"h1[itemprop='headline']",
		".fxs_headline h1",
		".fxs_article_title",
		"main h1",
		".content h1",
	}

	for _, sel := range selectors {
		if text := strings.TrimSpace(doc.Find(sel).First().Text()); text != "" {
			return text
		}
	}

	if text := strings.TrimSpace(doc.Find("h1").First().Text()); text != "" {
		return text
	}

	title := strings.TrimSpace(doc.Find("title").First().Text())

	for _, sep := range []string{" | ", " - ", " :: "} {
		if idx := strings.Index(title, sep); idx > 0 {
			return strings.TrimSpace(title[:idx])
		}
	}
	
	return title
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
		".fxs_article_content",
		".post-body",
		"main article",
		".entry",
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
	doc.Find("article p, .article p, main p").Each(func(_ int, s *goquery.Selection) {
		text := strings.TrimSpace(s.Text())
		if text != "" && len(text) > 20 {
			paragraphs = append(paragraphs, text)
		}
	})
	if joined := strings.Join(paragraphs, "\n\n"); len(joined) > 200 {
		return joined
	}

	var longParagraphs []string
	doc.Find("p").Each(func(_ int, s *goquery.Selection) {
		text := strings.TrimSpace(s.Text())
		if len(text) > 50 && !strings.Contains(text, "©") && !strings.Contains(text, "cookie") {
			parent := s.Parent()
			parentClass := parent.AttrOr("class", "")
			parentId := parent.AttrOr("id", "")
			
			if !strings.Contains(parentClass, "nav") && 
			   !strings.Contains(parentClass, "menu") &&
			   !strings.Contains(parentClass, "footer") &&
			   !strings.Contains(parentClass, "header") &&
			   !strings.Contains(parentClass, "sidebar") &&
			   !strings.Contains(parentId, "nav") &&
			   !strings.Contains(parentId, "menu") &&
			   !strings.Contains(parentId, "footer") {
				longParagraphs = append(longParagraphs, text)
			}
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