package collector

import (
	"encoding/xml"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"regexp"
	"strings"
	"sync"
	"time"

	"golang.org/x/net/html"
)

type Tweet struct {
	ID             string   `json:"id"`
	Text           string   `json:"text"`
	AuthorID       string   `json:"author_id"`
	AuthorUsername string   `json:"author_username"`
	AuthorName     string   `json:"author_name"`
	AuthorAvatar   string   `json:"author_avatar"`
	CreatedAt      string   `json:"created_at"`
	URL            string   `json:"url"`
	MediaURLs      []string `json:"media_urls,omitempty"`
}

type rssFeed struct {
	XMLName xml.Name   `xml:"rss"`
	Channel rssChannel `xml:"channel"`
}

type rssChannel struct {
	Title       string    `xml:"title"`
	Link        string    `xml:"link"`
	Description string    `xml:"description"`
	Image       *rssImage `xml:"image"`
	Items       []rssItem `xml:"item"`
}

type rssImage struct {
	URL string `xml:"url"`
}

type rssItem struct {
	Title       string `xml:"title"`
	Description string `xml:"description"`
	Link        string `xml:"link"`
	PubDate     string `xml:"pubDate"`
	GUID        string `xml:"guid"`
	Author      string `xml:"author"`
}

var tweetIDRegex = regexp.MustCompile(`/status/(\d+)`)

type TwitterCollector struct {
	rsshubURL string
	client    *http.Client
	lastSeenIDs map[string]string
	mu          sync.RWMutex
}

func NewTwitterCollector(rsshubURL string, timeout time.Duration) *TwitterCollector {
	// Strip trailing slash
	rsshubURL = strings.TrimRight(rsshubURL, "/")

	return &TwitterCollector{
		rsshubURL: rsshubURL,
		client: &http.Client{
			Timeout: timeout,
		},
		lastSeenIDs: make(map[string]string),
	}
}

func (c *TwitterCollector) FetchTweets(usernames string) []Tweet {
	if c.rsshubURL == "" || usernames == "" {
		return nil
	}

	names := strings.Split(usernames, ",")
	for i := range names {
		names[i] = strings.TrimSpace(names[i])
	}

	var allTweets []Tweet

	for _, name := range names {
		if name == "" {
			continue
		}

		tweets := c.fetchUserFeed(name)
		allTweets = append(allTweets, tweets...)
	}

	slog.Info("twitter: fetch completed", "tweets", len(allTweets), "users", len(names))
	return allTweets
}

func (c *TwitterCollector) fetchUserFeed(username string) []Tweet {
	feedURL := fmt.Sprintf("%s/twitter/user/%s", c.rsshubURL, username)

	resp, err := c.client.Get(feedURL)
	if err != nil {
		slog.Error("twitter: rsshub fetch failed", "user", username, "error", err)
		return nil
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 200))
		slog.Error("twitter: rsshub returned error",
			"user", username,
			"status", resp.StatusCode,
			"body", string(body),
		)
		return nil
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		slog.Error("twitter: read body failed", "user", username, "error", err)
		return nil
	}

	var feed rssFeed
	if err := xml.Unmarshal(body, &feed); err != nil {
		slog.Error("twitter: parse RSS failed", "user", username, "error", err)
		return nil
	}

	c.mu.RLock()
	lastSeenID := c.lastSeenIDs[strings.ToLower(username)]
	c.mu.RUnlock()

	// Extract author info from channel
	authorName := feed.Channel.Title
	// RSSHub title format: "username (@username) - X (�)"
	if idx := strings.Index(authorName, " - "); idx > 0 {
		authorName = authorName[:idx]
	}
	authorAvatar := ""
	if feed.Channel.Image != nil {
		authorAvatar = feed.Channel.Image.URL
	}

	var tweets []Tweet
	var newestID string

	for _, item := range feed.Channel.Items {
		tweetID := extractTweetID(item.Link)
		if tweetID == "" {
			tweetID = item.GUID
		}
		if tweetID == "" {
			continue
		}

		// Track newest for next poll
		if newestID == "" {
			newestID = tweetID
		}

		// Skip already-seen tweets
		if lastSeenID != "" && tweetID == lastSeenID {
			break // RSS items are sorted newest-first; stop at last seen
		}

		text := extractText(item.Description)
		mediaURLs := extractImages(item.Description)

		createdAt := parseRSSDate(item.PubDate)

		tweets = append(tweets, Tweet{
			ID:             tweetID,
			Text:           text,
			AuthorID:       username, // RSSHub doesn't provide numeric ID
			AuthorUsername: username,
			AuthorName:     authorName,
			AuthorAvatar:   authorAvatar,
			CreatedAt:      createdAt,
			URL:            item.Link,
			MediaURLs:      mediaURLs,
		})
	}

	// Update last seen
	if newestID != "" {
		c.mu.Lock()
		c.lastSeenIDs[strings.ToLower(username)] = newestID
		c.mu.Unlock()
	}

	slog.Info("twitter: fetched tweets", "user", username, "count", len(tweets))
	return tweets
}

func extractTweetID(link string) string {
	matches := tweetIDRegex.FindStringSubmatch(link)
	if len(matches) >= 2 {
		return matches[1]
	}
	return ""
}

// extractText strips HTML tags from RSS description to get plain text.
func extractText(htmlContent string) string {
	doc, err := html.Parse(strings.NewReader(htmlContent))
	if err != nil {
		// Fallback: strip tags naively
		return stripTags(htmlContent)
	}

	var sb strings.Builder
	var f func(*html.Node)
	f = func(n *html.Node) {
		if n.Type == html.TextNode {
			sb.WriteString(n.Data)
		}
		if n.Type == html.ElementNode && (n.Data == "br" || n.Data == "p") {
			sb.WriteString("\n")
		}
		for c := n.FirstChild; c != nil; c = c.NextSibling {
			f(c)
		}
	}
	f(doc)

	text := strings.TrimSpace(sb.String())
	// Collapse multiple newlines
	for strings.Contains(text, "\n\n\n") {
		text = strings.ReplaceAll(text, "\n\n\n", "\n\n")
	}
	return text
}

// extractImages finds <img> src attributes in HTML content.
func extractImages(htmlContent string) []string {
	doc, err := html.Parse(strings.NewReader(htmlContent))
	if err != nil {
		return nil
	}

	var urls []string
	var f func(*html.Node)
	f = func(n *html.Node) {
		if n.Type == html.ElementNode && n.Data == "img" {
			for _, attr := range n.Attr {
				if attr.Key == "src" && attr.Val != "" {
					urls = append(urls, attr.Val)
				}
			}
		}
		if n.Type == html.ElementNode && n.Data == "video" {
			for _, attr := range n.Attr {
				if attr.Key == "poster" && attr.Val != "" {
					urls = append(urls, attr.Val)
				}
			}
		}
		for c := n.FirstChild; c != nil; c = c.NextSibling {
			f(c)
		}
	}
	f(doc)

	return urls
}

func stripTags(s string) string {
	var result strings.Builder
	inTag := false
	for _, r := range s {
		if r == '<' {
			inTag = true
			continue
		}
		if r == '>' {
			inTag = false
			continue
		}
		if !inTag {
			result.WriteRune(r)
		}
	}
	return result.String()
}

func parseRSSDate(dateStr string) string {
	if dateStr == "" {
		return ""
	}

	// RFC2822 / RFC1123 (common RSS date formats)
	formats := []string{
		time.RFC1123Z,
		time.RFC1123,
		"Mon, 02 Jan 2006 15:04:05 -0700",
		"Mon, 02 Jan 2006 15:04:05 MST",
		time.RFC3339,
	}

	for _, format := range formats {
		if t, err := time.Parse(format, dateStr); err == nil {
			return t.UTC().Format(time.RFC3339)
		}
	}

	slog.Warn("twitter: unparseable date", "date", dateStr)
	return dateStr
}
