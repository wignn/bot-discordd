package pipeline

import (
	"context"
	"log/slog"
	"strconv"
	"strings"
	"time"

	"github.com/wign/news-server/internal/infoway"
	"github.com/wign/news-server/internal/ws"
)

type InfowayPipeline struct {
	clients []*infoway.Client
	hub     *ws.Hub
}

func NewInfowayPipeline(apiKey string, forexSymbols, cryptoSymbols string, hub *ws.Hub) *InfowayPipeline {
	var clients []*infoway.Client

	if forexSymbols != "" {
		clients = append(clients, infoway.NewClient(apiKey, infoway.BusinessCommon, forexSymbols))
	}

	if cryptoSymbols != "" {
		clients = append(clients, infoway.NewClient(apiKey, infoway.BusinessCrypto, cryptoSymbols))
	}

	return &InfowayPipeline{
		clients: clients,
		hub:     hub,
	}
}

func (p *InfowayPipeline) Run(ctx context.Context) {
	slog.Info("infoway pipeline starting", "connections", len(p.clients))

	for _, c := range p.clients {
		client := c
		go client.Run(ctx)
		go p.consumeTrades(ctx, client)
	}

	<-ctx.Done()
	slog.Info("infoway pipeline stopped")
}

func (p *InfowayPipeline) consumeTrades(ctx context.Context, client *infoway.Client) {
	for {
		select {
		case <-ctx.Done():
			return
		case trade := <-client.Trades():
			p.broadcastTrade(client.Business(), trade)
		}
	}
}

func (p *InfowayPipeline) broadcastTrade(business string, trade infoway.TradeData) {
	direction := "neutral"
	switch trade.Direction {
	case infoway.DirectionBuy:
		direction = "buy"
	case infoway.DirectionSell:
		direction = "sell"
	}

	assetType := "forex"
	if business == infoway.BusinessCrypto {
		assetType = "crypto"
	} else if business == infoway.BusinessStock {
		assetType = "stock"
	}

	price, _ := strconv.ParseFloat(trade.Price, 64)
	volume, _ := strconv.ParseFloat(trade.Volume, 64)

	tradeTime := time.UnixMilli(trade.Timestamp).UTC().Format(time.RFC3339)

	data := map[string]interface{}{
		"symbol":     trade.Symbol,
		"price":      price,
		"price_str":  trade.Price,
		"volume":     volume,
		"volume_str": trade.Volume,
		"value":      trade.Value,
		"direction":  direction,
		"asset_type": assetType,
		"business":   business,
		"trade_time": tradeTime,
		"timestamp":  trade.Timestamp,
	}

	channel := "market_data"
	if strings.HasSuffix(trade.Symbol, "USDT") || strings.HasSuffix(trade.Symbol, "BTC") {
		channel = "market_data"
	}

	GetPriceCache().Update(trade.Symbol, price, trade.Price, direction, assetType, trade.Volume, trade.Timestamp)

	p.hub.Broadcast(ws.EventMarketTrade, data, channel)
}
