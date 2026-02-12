package api

import (
	"encoding/json"
	"net/http"
	"time"
	"github.com/wign/news-server/internal/scraper"
)
func RegisterScrapingRoutes(mux *http.ServeMux){
	mux.HandleFunc("POST /api/v1/scraping", HandleScrapingNews())
}
func HandleScrapingNews() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}
		type requestBody struct {
			Link string `json:"link"`
		}
		var body requestBody
		err := json.NewDecoder(r.Body).Decode(&body)
		if err != nil {
			http.Error(w, "Failed to parse JSON", http.StatusBadRequest)
			return
		}
		if body.Link == "" {
			http.Error(w, "Link is required", http.StatusBadRequest)
			return
		}
		userAgent := "Mozilla/5.0"
		timeout := 10 * time.Second
		
		s := scraper.NewArticleScraper(userAgent, timeout)
		rs, err := s.Scrape(r.Context(), body.Link)
		if err != nil {
			http.Error(w, "Failed to scrape article: "+err.Error(), http.StatusInternalServerError)
			return
		}
		writeJSON(w, http.StatusOK, map[string] interface{}{
			"title": rs.Title,
			"content":rs.Content,
			"published_at":rs.PublishedAt,
			"tags":rs.Tags,
		})

	}
}
