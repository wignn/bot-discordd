package collector

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"net/http"
	"strings"
	"sync"
	"time"
)

const (
	forexFactoryURL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
	cacheTTL        = 2 * time.Hour
)

var wibLoc = time.FixedZone("WIB", 7*3600)

type CalendarEvent struct {
	Title        string
	Country      string
	Currency     string
	DateUTC      time.Time
	DateWIB      string
	Impact       string
	Forecast     string
	Previous     string
	EventID      string
	MinutesUntil int
}

type CalendarCollector struct {
	client *http.Client

	mu        sync.RWMutex
	cache     []CalendarEvent
	cacheTime time.Time
}

func NewCalendarCollector(timeout time.Duration) *CalendarCollector {
	return &CalendarCollector{
		client: &http.Client{Timeout: timeout},
	}
}

func (c *CalendarCollector) FetchEvents(ctx context.Context, forceRefresh bool) ([]CalendarEvent, error) {
	if !forceRefresh {
		c.mu.RLock()
		if len(c.cache) > 0 && time.Since(c.cacheTime) < cacheTTL {
			events := make([]CalendarEvent, len(c.cache))
			copy(events, c.cache)
			c.mu.RUnlock()
			slog.Debug("using cached calendar events", "count", len(events))
			return events, nil
		}
		c.mu.RUnlock()
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, forexFactoryURL, nil)
	if err != nil {
		return c.staleOrEmpty(), fmt.Errorf("create request: %w", err)
	}

	resp, err := c.client.Do(req)
	if err != nil {
		return c.staleOrEmpty(), fmt.Errorf("fetch calendar: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return c.staleOrEmpty(), fmt.Errorf("calendar returned %d", resp.StatusCode)
	}

	var rawEvents []rawCalendarEvent
	if err := json.NewDecoder(resp.Body).Decode(&rawEvents); err != nil {
		return c.staleOrEmpty(), fmt.Errorf("decode calendar: %w", err)
	}

	var events []CalendarEvent
	for _, raw := range rawEvents {
		if ev := parseCalendarEvent(raw); ev != nil {
			events = append(events, *ev)
		}
	}

	c.mu.Lock()
	c.cache = events
	c.cacheTime = time.Now()
	c.mu.Unlock()

	slog.Info("fetched calendar events", "count", len(events))
	return events, nil
}

func (c *CalendarCollector) GetUpcomingHighImpact(ctx context.Context, minutesBefore, minutesWindow int) ([]CalendarEvent, error) {
	events, err := c.FetchEvents(ctx, false)
	if err != nil {
		return nil, err
	}

	now := time.Now().UTC()
	var upcoming []CalendarEvent

	for _, ev := range events {
		impact := strings.ToLower(ev.Impact)
		if impact != "high" && impact != "red" {
			continue
		}

		mins := int(ev.DateUTC.Sub(now).Minutes())
		minBound := minutesBefore - minutesWindow
		maxBound := minutesBefore

		if mins >= minBound && mins <= maxBound {
			ev.MinutesUntil = mins
			upcoming = append(upcoming, ev)
		}
	}

	if len(upcoming) > 0 {
		titles := make([]string, len(upcoming))
		for i, e := range upcoming {
			titles[i] = e.Title
		}
		slog.Info("upcoming high-impact events", "count", len(upcoming), "events", titles)
	}

	return upcoming, nil
}

func (c *CalendarCollector) staleOrEmpty() []CalendarEvent {
	c.mu.RLock()
	defer c.mu.RUnlock()
	if len(c.cache) > 0 {
		slog.Warn("returning stale calendar cache")
		return c.cache
	}
	return nil
}

type rawCalendarEvent struct {
	Title    string `json:"title"`
	Country  string `json:"country"`
	Date     string `json:"date"`
	Impact   string `json:"impact"`
	Forecast string `json:"forecast"`
	Previous string `json:"previous"`
}

var currencyMap = map[string]string{
	"USD": "USD 🇺🇸", "EUR": "EUR 🇪🇺", "GBP": "GBP 🇬🇧",
	"JPY": "JPY 🇯🇵", "CHF": "CHF 🇨🇭", "AUD": "AUD 🇦🇺",
	"NZD": "NZD 🇳🇿", "CAD": "CAD 🇨🇦", "CNY": "CNY 🇨🇳",
}

func parseCalendarEvent(raw rawCalendarEvent) *CalendarEvent {
	title := strings.TrimSpace(raw.Title)
	country := strings.TrimSpace(raw.Country)
	if title == "" || raw.Date == "" {
		return nil
	}

	dateUTC, err := time.Parse(time.RFC3339, raw.Date)
	if err != nil {
		dateUTC, err = time.Parse("2006-01-02T15:04:05", raw.Date)
		if err != nil {
			return nil
		}
		dateUTC = dateUTC.UTC()
	}
	dateUTC = dateUTC.UTC()

	dateWIB := dateUTC.In(wibLoc)
	dateWIBStr := dateWIB.Format("02/01 15:04") + " WIB"

	currency := country
	if mapped, ok := currencyMap[strings.ToUpper(country)]; ok {
		currency = mapped
	}

	forecast := strings.TrimSpace(raw.Forecast)
	if forecast == "" {
		forecast = "—"
	}
	previous := strings.TrimSpace(raw.Previous)
	if previous == "" {
		previous = "—"
	}

	eventID := fmt.Sprintf("%s_%s_%s", raw.Date, country, truncate(title, 30))

	return &CalendarEvent{
		Title:    title,
		Country:  country,
		Currency: currency,
		DateUTC:  dateUTC,
		DateWIB:  dateWIBStr,
		Impact:   strings.TrimSpace(raw.Impact),
		Forecast: forecast,
		Previous: previous,
		EventID:  eventID,
	}
}

func truncate(s string, maxLen int) string {
	if len(s) > maxLen {
		return s[:maxLen]
	}
	return s
}
