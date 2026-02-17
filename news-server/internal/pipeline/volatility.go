package pipeline

import (
	"context"
	"fmt"
	"log/slog"
	"math"
	"sync"
	"time"

	"github.com/wign/news-server/internal/ws"
)

const (
	atrPeriod         = 14
	atrAvgWindow      = 50
	spikeMultiplier   = 2.0
	alertCooldownMins = 30
	tickIntervalSec   = 60
	xauSymbol         = "XAUUSD"
)

type candle struct {
	High  float64
	Low   float64
	Close float64
}

type VolatilityPipeline struct {
	hub           *ws.Hub
	mu            sync.Mutex
	candles       []candle
	atrHistory    []float64
	lastPrice     float64
	minuteHigh    float64
	minuteLow     float64
	lastAlertTime time.Time
}

func NewVolatilityPipeline(hub *ws.Hub) *VolatilityPipeline {
	return &VolatilityPipeline{
		hub:     hub,
		candles: make([]candle, 0, atrPeriod+atrAvgWindow+10),
	}
}

func (v *VolatilityPipeline) Run(ctx context.Context) {
	slog.Info("volatility pipeline starting", "symbol", xauSymbol, "atr_period", atrPeriod)

	ticker := time.NewTicker(tickIntervalSec * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			slog.Info("volatility pipeline stopped")
			return
		case <-ticker.C:
			v.tick()
		}
	}
}

func (v *VolatilityPipeline) tick() {
	entry := GetPriceCache().Get(xauSymbol)
	if entry == nil || entry.Price <= 0 {
		return
	}

	v.mu.Lock()
	defer v.mu.Unlock()

	price := entry.Price

	if v.lastPrice == 0 {
		v.lastPrice = price
		v.minuteHigh = price
		v.minuteLow = price
		return
	}

	if price > v.minuteHigh {
		v.minuteHigh = price
	}
	if price < v.minuteLow || v.minuteLow == 0 {
		v.minuteLow = price
	}

	c := candle{
		High:  v.minuteHigh,
		Low:   v.minuteLow,
		Close: price,
	}
	v.candles = append(v.candles, c)

	v.lastPrice = price
	v.minuteHigh = price
	v.minuteLow = price

	maxCandles := atrPeriod + atrAvgWindow + 20
	if len(v.candles) > maxCandles {
		v.candles = v.candles[len(v.candles)-maxCandles:]
	}

	if len(v.candles) < atrPeriod+1 {
		return
	}

	currentATR := v.calculateATR(v.candles)
	v.atrHistory = append(v.atrHistory, currentATR)

	if len(v.atrHistory) > atrAvgWindow+10 {
		v.atrHistory = v.atrHistory[len(v.atrHistory)-(atrAvgWindow+10):]
	}

	if len(v.atrHistory) < atrAvgWindow {
		return
	}

	avgATR := v.averageATR()
	if avgATR <= 0 {
		return
	}

	ratio := currentATR / avgATR

	slog.Debug("volatility check",
		"symbol", xauSymbol,
		"price", price,
		"current_atr", math.Round(currentATR*100)/100,
		"avg_atr", math.Round(avgATR*100)/100,
		"ratio", math.Round(ratio*100)/100,
	)

	if ratio >= spikeMultiplier {
		if time.Since(v.lastAlertTime) < alertCooldownMins*time.Minute {
			slog.Debug("volatility spike detected but in cooldown",
				"ratio", ratio,
				"cooldown_remaining", alertCooldownMins*time.Minute-time.Since(v.lastAlertTime),
			)
			return
		}

		v.lastAlertTime = time.Now()
		v.broadcastAlert(price, currentATR, avgATR, ratio)
	}
}

func (v *VolatilityPipeline) calculateATR(candles []candle) float64 {
	n := len(candles)
	if n < atrPeriod+1 {
		return 0
	}

	var atr float64
	start := n - atrPeriod
	for i := start; i < n; i++ {
		c := candles[i]
		prevClose := candles[i-1].Close

		tr1 := c.High - c.Low
		tr2 := math.Abs(c.High - prevClose)
		tr3 := math.Abs(c.Low - prevClose)

		tr := math.Max(tr1, math.Max(tr2, tr3))
		atr += tr
	}

	return atr / float64(atrPeriod)
}

func (v *VolatilityPipeline) averageATR() float64 {
	n := len(v.atrHistory)
	if n < atrAvgWindow {
		return 0
	}

	var sum float64
	for i := n - atrAvgWindow; i < n-1; i++ {
		sum += v.atrHistory[i]
	}
	return sum / float64(atrAvgWindow-1)
}

func (v *VolatilityPipeline) broadcastAlert(price, currentATR, avgATR, ratio float64) {
	slog.Warn("GOLD VOLATILITY SPIKE DETECTED",
		"symbol", xauSymbol,
		"price", price,
		"current_atr", currentATR,
		"avg_atr", avgATR,
		"ratio", ratio,
	)

	data := map[string]interface{}{
		"symbol":      xauSymbol,
		"price":       price,
		"current_atr": math.Round(currentATR*100) / 100,
		"avg_atr":     math.Round(avgATR*100) / 100,
		"ratio":       math.Round(ratio*100) / 100,
		"message":     "WARNING: abnormal volatility detected",
		"discord_embed": map[string]interface{}{
			"title":       "GOLD VOLATILITY SPIKE",
			"description": "WARNING: abnormal volatility detected on XAUUSD. Current ATR significantly exceeds historical average. Exercise extreme caution.",
			"color":       0xFF0000,
			"fields": []map[string]interface{}{
				{"name": "Symbol", "value": xauSymbol, "inline": true},
				{"name": "Price", "value": formatPrice(price), "inline": true},
				{"name": "ATR Ratio", "value": formatRatio(ratio), "inline": true},
				{"name": "Current ATR", "value": formatPrice(currentATR), "inline": true},
				{"name": "Avg ATR", "value": formatPrice(avgATR), "inline": true},
				{"name": "Status", "value": "ABNORMAL", "inline": true},
			},
			"footer": map[string]interface{}{
				"text": "Fio Volatility Detector",
			},
		},
	}

	count := v.hub.Broadcast(ws.EventGoldVolatilitySpike, data, "volatility")
	slog.Info("volatility alert broadcast", "clients", count)
}

func formatPrice(v float64) string {
	return fmt.Sprintf("$%.2f", v)
}

func formatRatio(v float64) string {
	return fmt.Sprintf("%.2fx", v)
}
