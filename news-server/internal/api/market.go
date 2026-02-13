package api

import (
	"net/http"

	"github.com/wign/news-server/internal/pipeline"
)

func RegisterMarketRoutes(mux *http.ServeMux) {
	mux.HandleFunc("GET /api/v1/market/prices", handleGetPrices)
	mux.HandleFunc("GET /api/v1/market/price/{symbol}", handleGetPrice)
}

func handleGetPrices(w http.ResponseWriter, r *http.Request) {
	cache := pipeline.GetPriceCache()
	prices := cache.GetAll()

	result := make([]interface{}, 0, len(prices))
	for _, p := range prices {
		result = append(result, p)
	}

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"prices": result,
		"count":  len(result),
	})
}

func handleGetPrice(w http.ResponseWriter, r *http.Request) {
	symbol := r.PathValue("symbol")
	if symbol == "" {
		writeJSON(w, http.StatusBadRequest, map[string]interface{}{
			"error": "symbol is required",
		})
		return
	}

	cache := pipeline.GetPriceCache()
	entry := cache.Get(symbol)

	if entry == nil {
		writeJSON(w, http.StatusNotFound, map[string]interface{}{
			"error":  "symbol not found",
			"symbol": symbol,
		})
		return
	}

	writeJSON(w, http.StatusOK, entry)
}
