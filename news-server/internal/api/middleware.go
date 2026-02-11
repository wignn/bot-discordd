package api

import (
	"log/slog"
	"net/http"
	"strings"
)

type APIKeyMiddleware struct {
	keys map[string]bool
}

func NewAPIKeyMiddleware(keyList string) *APIKeyMiddleware {
	m := &APIKeyMiddleware{keys: make(map[string]bool)}
	for _, k := range strings.Split(keyList, ",") {
		k = strings.TrimSpace(k)
		if k != "" {
			m.keys[k] = true
		}
	}
	return m
}

func (m *APIKeyMiddleware) Wrap(next http.Handler) http.Handler {
	if len(m.keys) == 0 {
		slog.Warn("no API keys configured, all requests allowed")
		return next
	}

	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/health" || r.URL.Path == "/" {
			next.ServeHTTP(w, r)
			return
		}

		if r.Method == "GET" && (strings.HasPrefix(r.URL.Path, "/api/v1/news") ||
			strings.HasPrefix(r.URL.Path, "/api/v1/stock") ||
			strings.HasPrefix(r.URL.Path, "/api/v1/stream")) {
			next.ServeHTTP(w, r)
			return
		}

		key := r.Header.Get("X-API-Key")
		if key == "" {
			key = r.URL.Query().Get("api_key")
		}
		if key == "" {
			key = r.URL.Query().Get("token")
		}

		if !m.keys[key] {
			http.Error(w, `{"error":"invalid or missing API key"}`, http.StatusUnauthorized)
			return
		}

		next.ServeHTTP(w, r)
	})
}
