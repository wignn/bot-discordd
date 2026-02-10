package api

import (
	"encoding/json"
	"log/slog"
	"net/http"
	"strconv"

	"github.com/jackc/pgx/v5/pgxpool"
)

func RegisterNewsRoutes(mux *http.ServeMux, db *pgxpool.Pool) {
	mux.HandleFunc("GET /api/v1/news", handleListNews(db))
	mux.HandleFunc("GET /api/v1/news/latest", handleLatestNews(db))
	mux.HandleFunc("GET /api/v1/news/{id}", handleGetNews(db))
}

func handleListNews(db *pgxpool.Pool) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		page, _ := strconv.Atoi(r.URL.Query().Get("page"))
		if page < 1 {
			page = 1
		}
		pageSize, _ := strconv.Atoi(r.URL.Query().Get("page_size"))
		if pageSize < 1 || pageSize > 100 {
			pageSize = 20
		}
		offset := (page - 1) * pageSize

		rows, err := db.Query(r.Context(),
			`SELECT id, source_id, content_hash, original_url, original_title,
				summary, is_processed, processed_at, published_at
			 FROM news_articles
			 ORDER BY processed_at DESC NULLS LAST
			 LIMIT $1 OFFSET $2`, pageSize, offset)
		if err != nil {
			slog.Error("list news query failed", "error", err)
			writeJSON(w, http.StatusInternalServerError, map[string]interface{}{"error": "query failed"})
			return
		}
		defer rows.Close()

		var items []map[string]interface{}
		for rows.Next() {
			var id, contentHash, url, title string
			var sourceID, summary interface{}
			var isProcessed bool
			var processedAt, publishedAt interface{}

			if err := rows.Scan(&id, &sourceID, &contentHash, &url, &title,
				&summary, &isProcessed, &processedAt, &publishedAt); err != nil {
				continue
			}

			items = append(items, map[string]interface{}{
				"id":             id,
				"content_hash":   contentHash,
				"original_url":   url,
				"original_title": title,
				"summary":        summary,
				"is_processed":   isProcessed,
				"processed_at":   processedAt,
				"published_at":   publishedAt,
			})
		}

		if items == nil {
			items = []map[string]interface{}{}
		}

		// Count total
		var total int
		db.QueryRow(r.Context(), `SELECT COUNT(*) FROM news_articles`).Scan(&total)

		totalPages := (total + pageSize - 1) / pageSize
		writeJSON(w, http.StatusOK, map[string]interface{}{
			"items":       items,
			"total":       total,
			"page":        page,
			"page_size":   pageSize,
			"total_pages": totalPages,
		})
	}
}

func handleLatestNews(db *pgxpool.Pool) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
		if limit < 1 || limit > 50 {
			limit = 10
		}

		rows, err := db.Query(r.Context(),
			`SELECT id, content_hash, original_url, original_title,
				summary, published_at, processed_at
			 FROM news_articles
			 WHERE is_processed = TRUE
			 ORDER BY processed_at DESC NULLS LAST
			 LIMIT $1`, limit)
		if err != nil {
			slog.Error("latest news query failed", "error", err)
			writeJSON(w, http.StatusInternalServerError, map[string]interface{}{"error": "query failed"})
			return
		}
		defer rows.Close()

		var items []map[string]interface{}
		for rows.Next() {
			var id, contentHash, url, title string
			var summary, publishedAt, processedAt interface{}

			if err := rows.Scan(&id, &contentHash, &url, &title,
				&summary, &publishedAt, &processedAt); err != nil {
				continue
			}

			items = append(items, map[string]interface{}{
				"id":             id,
				"content_hash":   contentHash,
				"original_url":   url,
				"original_title": title,
				"summary":        summary,
				"published_at":   publishedAt,
				"processed_at":   processedAt,
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

func handleGetNews(db *pgxpool.Pool) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id := r.PathValue("id")

		var contentHash, url, title string
		var sourceID, summary, content, publishedAt, processedAt interface{}
		var isProcessed bool

		err := db.QueryRow(r.Context(),
			`SELECT id, source_id, content_hash, original_url, original_title,
				original_content, summary, is_processed, processed_at, published_at
			 FROM news_articles WHERE id = $1`, id).
			Scan(&id, &sourceID, &contentHash, &url, &title,
				&content, &summary, &isProcessed, &processedAt, &publishedAt)
		if err != nil {
			writeJSON(w, http.StatusNotFound, map[string]interface{}{"error": "article not found"})
			return
		}

		writeJSON(w, http.StatusOK, map[string]interface{}{
			"id":               id,
			"source_id":        sourceID,
			"content_hash":     contentHash,
			"original_url":     url,
			"original_title":   title,
			"original_content": content,
			"summary":          summary,
			"is_processed":     isProcessed,
			"processed_at":     processedAt,
			"published_at":     publishedAt,
		})
	}
}

func writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}
