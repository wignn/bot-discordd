package api

import (
	"fmt"
	"log/slog"
	"net/http"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/wign/news-server/internal/ws"
)

type Server struct {
	hub  *ws.Hub
	db   *pgxpool.Pool
	port int
	auth *APIKeyMiddleware
}

func NewServer(hub *ws.Hub, db *pgxpool.Pool, port int, apiKeys string) *Server {
	return &Server{
		hub:  hub,
		db:   db,
		port: port,
		auth: NewAPIKeyMiddleware(apiKeys),
	}
}

func (s *Server) Start() error {
	mux := http.NewServeMux()

	// Health check (no auth)
	mux.HandleFunc("GET /health", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]interface{}{
			"status":  "healthy",
			"service": "news-server",
		})
	})
	mux.HandleFunc("GET /", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/" {
			http.NotFound(w, r)
			return
		}
		writeJSON(w, http.StatusOK, map[string]interface{}{
			"service": "Forex News Server (Go)",
			"version": "2.0.0",
		})
	})

	// WebSocket
	mux.HandleFunc("/api/v1/stream/ws/discord", s.hub.HandleWS)
	mux.HandleFunc("/api/v1/stream/ws", s.hub.HandleWS)

	// REST API
	RegisterNewsRoutes(mux, s.db)
	RegisterStockRoutes(mux, s.db)

	// Wrap with auth + CORS
	handler := corsMiddleware(s.auth.Wrap(mux))

	addr := fmt.Sprintf(":%d", s.port)
	slog.Info("HTTP server starting", "addr", addr)
	return http.ListenAndServe(addr, handler)
}

func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, X-API-Key, Authorization")

		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusNoContent)
			return
		}

		next.ServeHTTP(w, r)
	})
}
