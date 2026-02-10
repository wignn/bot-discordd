package ws

import (
	"fmt"
	"time"
)

var wib *time.Location

func init() {
	var err error
	wib, err = time.LoadLocation("Asia/Jakarta")
	if err != nil {
		wib = time.FixedZone("WIB", 7*3600)
	}
}

const (
	EventNewsNew          = "news.new"
	EventNewsHighImpact   = "news.high_impact"
	EventStockNewsNew     = "stock.news.new"
	EventCalendarReminder = "calendar.reminder"
	EventHeartbeat        = "heartbeat"
	EventSystemStatus     = "system.status"
)

type NewsArticleData struct {
	ID          string `json:"id"`
	Title       string `json:"original_title"`
	TitleID     string `json:"translated_title,omitempty"`
	Summary     string `json:"summary,omitempty"`
	SummaryID   string `json:"summary_id,omitempty"`
	SourceName  string `json:"source_name"`
	SourceURL   string `json:"source_url"`
	URL         string `json:"url"`
	Sentiment   string `json:"sentiment,omitempty"`
	ImpactLevel string `json:"impact_level,omitempty"`
	PublishedAt string `json:"published_at,omitempty"`
	ProcessedAt string `json:"processed_at"`
	ImageURL    string `json:"image_url,omitempty"`
}

func BuildNewsEmbed(a NewsArticleData) map[string]interface{} {
	color := 0x0099FF
	impactBar := "▰▰▰"

	timeStr := formatWIB(a.PublishedAt)
	footerDate := formatFooterDate(a.PublishedAt)

	displayTitle := a.TitleID
	if displayTitle == "" {
		displayTitle = a.Title
	}
	displaySummary := a.SummaryID
	if displaySummary == "" {
		displaySummary = a.Summary
	}
	if len(displaySummary) > 300 {
		displaySummary = displaySummary[:300]
	}

	desc := fmt.Sprintf("**MARKET**\n%s\n\n%s", displayTitle, displaySummary)

	return map[string]interface{}{
		"title":       displayTitle,
		"description": desc,
		"color":       color,
		"fields": []map[string]interface{}{
			{"name": "Waktu", "value": timeStr, "inline": true},
			{"name": "Impact", "value": impactBar, "inline": true},
			{"name": "Sumber", "value": fmt.Sprintf("[Baca Selengkapnya](%s)", a.URL), "inline": false},
		},
		"footer": map[string]interface{}{
			"text": fmt.Sprintf("Forex Alert • %s • %s", a.SourceName, footerDate),
		},
	}
}

type StockNewsData struct {
	ID          string   `json:"id"`
	Title       string   `json:"title"`
	Summary     string   `json:"summary,omitempty"`
	Content     string   `json:"content,omitempty"`
	SourceName  string   `json:"source_name"`
	SourceURL   string   `json:"source_url"`
	URL         string   `json:"url"`
	Category    string   `json:"category"`
	Tickers     []string `json:"tickers"`
	Sentiment   string   `json:"sentiment,omitempty"`
	ImpactLevel string   `json:"impact_level,omitempty"`
	PublishedAt string   `json:"published_at,omitempty"`
	ProcessedAt string   `json:"processed_at"`
}

func BuildStockEmbed(s StockNewsData) map[string]interface{} {
	color := 0x5865F2

	impactBars := map[string]string{"high": "▰▰▰", "medium": "▰▰▱", "low": "▰▱▱"}
	impactBar := impactBars[s.ImpactLevel]
	if impactBar == "" {
		impactBar = "▰▱▱"
	}

	timeStr := formatWIB(s.PublishedAt)
	footerDate := formatFooterDate(s.PublishedAt)

	cat := s.Category
	if cat == "" {
		cat = "MARKET"
	}

	summary := s.Summary
	if len(summary) > 300 {
		summary = summary[:300]
	}

	desc := fmt.Sprintf("**%s**\n%s\n\n%s", cat, s.Title, summary)

	fields := []map[string]interface{}{
		{"name": "Waktu", "value": timeStr, "inline": true},
		{"name": "Impact", "value": impactBar, "inline": true},
	}

	if len(s.Tickers) > 0 {
		t := ""
		for i, ticker := range s.Tickers {
			if i >= 5 {
				break
			}
			if i > 0 {
				t += ", "
			}
			t += ticker
		}
		fields = append(fields, map[string]interface{}{"name": "Tickers", "value": t, "inline": true})
	}

	fields = append(fields, map[string]interface{}{
		"name": "Sumber", "value": fmt.Sprintf("[Baca Selengkapnya](%s)", s.URL), "inline": false,
	})

	return map[string]interface{}{
		"title":       s.Title,
		"description": desc,
		"color":       color,
		"fields":      fields,
		"footer": map[string]interface{}{
			"text": fmt.Sprintf("Stock Alert • %s • %s", s.SourceName, footerDate),
		},
	}
}

func formatWIB(isoTime string) string {
	if isoTime == "" {
		return "N/A"
	}
	t, err := time.Parse(time.RFC3339, isoTime)
	if err != nil {
		return "N/A"
	}
	return t.In(wib).Format("15:04 WIB")
}

func formatFooterDate(isoTime string) string {
	if isoTime == "" {
		return ""
	}
	t, err := time.Parse(time.RFC3339, isoTime)
	if err != nil {
		return ""
	}
	return t.In(wib).Format("02/01/2006 15:04")
}
