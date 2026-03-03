package pipeline

import (
	"context"
	"fmt"
	"log/slog"
	"strings"
	"time"

	"github.com/wign/news-server/internal/mt5"
	"github.com/wign/news-server/internal/ws"
)

type MT5Pipeline struct {
	clients   []*mt5.Client
	hub       *ws.Hub
	symbolMap map[string]string 
}

func NewMT5Pipeline(wsURL, symbols, symbolMapStr string, hub *ws.Hub) *MT5Pipeline {
	symMap := parseSymbolMap(symbolMapStr)

	var clients []*mt5.Client
	for _, s := range splitSymbols(symbols) {
		clients = append(clients, mt5.NewClient(wsURL, s))
	}

	return &MT5Pipeline{
		clients:   clients,
		hub:       hub,
		symbolMap: symMap,
	}
}

func (p *MT5Pipeline) Run(ctx context.Context) {
	slog.Info("mt5 pipeline starting", "connections", len(p.clients))

	for _, c := range p.clients {
		client := c
		go client.Run(ctx)
		go p.consumeTicks(ctx, client)
	}

	<-ctx.Done()
	slog.Info("mt5 pipeline stopped")
}

func (p *MT5Pipeline) consumeTicks(ctx context.Context, client *mt5.Client) {
	var lastBid float64

	for {
		select {
		case <-ctx.Done():
			return
		case tick := <-client.Ticks():
			p.broadcastTick(tick, &lastBid)
		}
	}
}

func (p *MT5Pipeline) broadcastTick(tick mt5.Tick, lastBid *float64) {
	symbol := tick.Symbol
	if mapped, ok := p.symbolMap[symbol]; ok {
		symbol = mapped
	}
	direction := "neutral"
	if *lastBid > 0 {
		if tick.Bid > *lastBid {
			direction = "buy"
		} else if tick.Bid < *lastBid {
			direction = "sell"
		}
	}
	*lastBid = tick.Bid

	price := tick.Bid
	priceStr := formatMT5Price(price)

	tradeTime := time.Unix(tick.Time, 0).UTC().Format(time.RFC3339)
	timestamp := tick.TimeMsc
	if timestamp == 0 {
		timestamp = tick.Time * 1000
	}

	data := map[string]interface{}{
		"symbol":     symbol,
		"price":      price,
		"price_str":  priceStr,
		"volume":     tick.Volume,
		"volume_str": fmt.Sprintf("%.0f", tick.Volume),
		"direction":  direction,
		"asset_type": "forex",
		"business":   "common",
		"trade_time": tradeTime,
		"timestamp":  timestamp,
	}

	GetPriceCache().Update(symbol, price, priceStr, direction, "forex",
		fmt.Sprintf("%.0f", tick.Volume), timestamp)

	p.hub.Broadcast(ws.EventMarketTrade, data, "market_data")
}

func formatMT5Price(price float64) string {
	if price > 100 {
		return fmt.Sprintf("%.2f", price)
	}
	return fmt.Sprintf("%.5f", price)
}

func splitSymbols(s string) []string {
	var result []string
	for _, sym := range strings.Split(s, ",") {
		sym = strings.TrimSpace(sym)
		if sym != "" {
			result = append(result, sym)
		}
	}
	return result
}

func parseSymbolMap(s string) map[string]string {
	m := make(map[string]string)
	if s == "" {
		return m
	}
	for _, pair := range strings.Split(s, ",") {
		parts := strings.SplitN(strings.TrimSpace(pair), ":", 2)
		if len(parts) == 2 {
			m[strings.TrimSpace(parts[0])] = strings.TrimSpace(parts[1])
		}
	}
	return m
}
