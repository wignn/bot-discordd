package api

import (
	"log/slog"
	"net/http"
	"strconv"

	"github.com/jackc/pgx/v5/pgxpool"
)

func RegisterStockRoutes(mux *http.ServeMux, db *pgxpool.Pool) {
	mux.HandleFunc("GET /api/v1/stock/latest", handleLatestStockNews(db))
}

func handleLatestStockNews(db *pgxpool.Pool) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
		if limit < 1 || limit > 50 {
			limit = 10
		}

		rows, err := db.Query(r.Context(),
			`SELECT content_hash, title, summary, source_name,
				category, tickers, sentiment, impact_level, processed_at
			 FROM stock_news
			 WHERE is_processed = TRUE
			 ORDER BY processed_at DESC
			 LIMIT $1`, limit)
		if err != nil {
			slog.Error("stock news query failed", "error", err)
			writeJSON(w, http.StatusInternalServerError, map[string]interface{}{"error": "query failed"})
			return
		}
		defer rows.Close()

		var items []map[string]interface{}
		for rows.Next() {
			var contentHash, title string
			var summary, sourceName, category, tickers, sentiment, impactLevel interface{}
			var processedAt interface{}

			if err := rows.Scan(&contentHash, &title, &summary, &sourceName,
				&category, &tickers, &sentiment, &impactLevel, &processedAt); err != nil {
				continue
			}

			items = append(items, map[string]interface{}{
				"id":           contentHash,
				"content_hash": contentHash,
				"title":        title,
				"summary":      summary,
				"source_name":  sourceName,
				"category":     category,
				"tickers":      tickers,
				"sentiment":    sentiment,
				"impact_level": impactLevel,
				"published_at": processedAt,
				"processed_at": processedAt,
			})
		}

		if items == nil {
			items = []map[string]interface{}{}
		}

		writeJSON(w, http.StatusOK, map[string]interface{}{
			"items": items,
			"total": len(items),
		})
	}
}
