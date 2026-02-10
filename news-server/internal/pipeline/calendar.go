package pipeline

import (
	"context"
	"log/slog"

	"github.com/wign/news-server/internal/collector"
	"github.com/wign/news-server/internal/ws"
)

type CalendarPipeline struct {
	collector *collector.CalendarCollector
	hub       *ws.Hub
}

func NewCalendarPipeline(
	cal *collector.CalendarCollector,
	hub *ws.Hub,
) *CalendarPipeline {
	return &CalendarPipeline{
		collector: cal,
		hub:       hub,
	}
}

func (p *CalendarPipeline) Run(ctx context.Context) {
	slog.Debug("calendar pipeline: checking")

	events, err := p.collector.GetUpcomingHighImpact(ctx, 15, 5)
	if err != nil {
		slog.Error("calendar pipeline: failed", "error", err)
		return
	}

	if len(events) == 0 {
		slog.Debug("calendar pipeline: no upcoming events")
		return
	}

	broadcasted := 0
	for _, event := range events {
		data := map[string]interface{}{
			"event_id":      event.EventID,
			"title":         event.Title,
			"country":       event.Country,
			"currency":      event.Currency,
			"date_wib":      event.DateWIB,
			"impact":        event.Impact,
			"forecast":      event.Forecast,
			"previous":      event.Previous,
			"minutes_until": event.MinutesUntil,
		}

		count := p.hub.Broadcast(ws.EventCalendarReminder, data, "calendar")

		slog.Info("calendar broadcast ok",
			"event", event.Title,
			"clients", count,
			"minutes_until", event.MinutesUntil,
		)
		broadcasted++
	}

	slog.Info("calendar pipeline: completed",
		"events_found", len(events),
		"broadcasted", broadcasted,
	)
}
