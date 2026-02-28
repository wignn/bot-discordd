package pipeline

import (
	"context"
	"log/slog"
	"time"

	"github.com/wign/news-server/internal/collector"
	"github.com/wign/news-server/internal/ws"
)

type TwitterPipeline struct {
	collector *collector.TwitterCollector
	hub       *ws.Hub
	usernames string
	seeded    bool
}

func NewTwitterPipeline(
	tc *collector.TwitterCollector,
	hub *ws.Hub,
	usernames string,
) *TwitterPipeline {
	return &TwitterPipeline{
		collector: tc,
		hub:       hub,
		usernames: usernames,
	}
}

func (p *TwitterPipeline) Run(ctx context.Context, interval time.Duration) {
	slog.Info("twitter pipeline: starting", "interval", interval, "usernames", p.usernames)
	p.seed()

	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			slog.Info("twitter pipeline: stopping")
			return
		case <-ticker.C:
			p.tick()
		}
	}
}

func (p *TwitterPipeline) seed() {
	defer func() {
		if r := recover(); r != nil {
			slog.Error("twitter pipeline: seed panic recovered", "panic", r)
		}
	}()

	tweets := p.collector.FetchTweets(p.usernames)
	p.seeded = true
	slog.Info("twitter pipeline: seeded (skipped broadcast)", "tweets_seen", len(tweets))
}

func (p *TwitterPipeline) tick() {
	defer func() {
		if r := recover(); r != nil {
			slog.Error("twitter pipeline: panic recovered", "panic", r)
		}
	}()

	tweets := p.collector.FetchTweets(p.usernames)
	if len(tweets) == 0 {
		return
	}

	broadcasted := 0
	for _, tweet := range tweets {
		tweetData := ws.TwitterTweetData{
			ID:             tweet.ID,
			Text:           tweet.Text,
			AuthorUsername: tweet.AuthorUsername,
			AuthorName:     tweet.AuthorName,
			AuthorAvatar:   tweet.AuthorAvatar,
			CreatedAt:      tweet.CreatedAt,
			URL:            tweet.URL,
			MediaURLs:      tweet.MediaURLs,
		}

		embed := ws.BuildTwitterEmbed(tweetData)
		count := p.hub.Broadcast(ws.EventTwitterNew, map[string]interface{}{
			"tweet":         tweetData,
			"discord_embed": embed,
		}, "twitter")

		if count > 0 {
			broadcasted++
		}

		slog.Info("twitter: broadcast tweet",
			"author", tweet.AuthorUsername,
			"tweet_id", tweet.ID,
			"clients", count,
		)
	}

	slog.Info("twitter pipeline: tick completed", "total", len(tweets), "broadcasted", broadcasted)
}
