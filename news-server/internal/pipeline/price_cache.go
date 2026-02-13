package pipeline

import (
	"sync"
	"time"
)

type PriceEntry struct {
	Symbol    string  `json:"symbol"`
	Price     float64 `json:"price"`
	PriceStr  string  `json:"price_str"`
	Direction string  `json:"direction"`
	AssetType string  `json:"asset_type"`
	Volume    string  `json:"volume"`
	UpdatedAt string  `json:"updated_at"`
	Timestamp int64   `json:"timestamp"`
}

type PriceCache struct {
	mu     sync.RWMutex
	prices map[string]*PriceEntry
}

var globalPriceCache = &PriceCache{
	prices: make(map[string]*PriceEntry),
}

func GetPriceCache() *PriceCache {
	return globalPriceCache
}

func (c *PriceCache) Update(symbol string, price float64, priceStr, direction, assetType, volume string, timestamp int64) {
	c.mu.Lock()
	defer c.mu.Unlock()

	c.prices[symbol] = &PriceEntry{
		Symbol:    symbol,
		Price:     price,
		PriceStr:  priceStr,
		Direction: direction,
		AssetType: assetType,
		Volume:    volume,
		UpdatedAt: time.Now().UTC().Format(time.RFC3339),
		Timestamp: timestamp,
	}
}

func (c *PriceCache) Get(symbol string) *PriceEntry {
	c.mu.RLock()
	defer c.mu.RUnlock()

	if e, ok := c.prices[symbol]; ok {
		copy := *e
		return &copy
	}
	return nil
}

func (c *PriceCache) GetAll() map[string]*PriceEntry {
	c.mu.RLock()
	defer c.mu.RUnlock()

	result := make(map[string]*PriceEntry, len(c.prices))
	for k, v := range c.prices {
		copy := *v
		result[k] = &copy
	}
	return result
}
