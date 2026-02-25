package stats

import (
	"context"
	"encoding/json"
	"log/slog"
	"net/http"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

var upgrader = websocket.Upgrader{
	CheckOrigin:     func(r *http.Request) bool { return true },
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
}

type statsClient struct {
	hub  *StatsHub
	conn *websocket.Conn
	send chan []byte
}

type StatsHub struct {
	mu         sync.RWMutex
	clients    map[*statsClient]bool
	register   chan *statsClient
	unregister chan *statsClient
}

func NewStatsHub() *StatsHub {
	return &StatsHub{
		clients:    make(map[*statsClient]bool),
		register:   make(chan *statsClient),
		unregister: make(chan *statsClient),
	}
}

func (h *StatsHub) Run(ctx context.Context, interval time.Duration) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			h.mu.Lock()
			for c := range h.clients {
				close(c.send)
				delete(h.clients, c)
			}
			h.mu.Unlock()
			slog.Info("stats hub stopped")
			return

		case client := <-h.register:
			h.mu.Lock()
			h.clients[client] = true
			h.mu.Unlock()
			slog.Info("stats ws client connected", "total", h.clientCount())

		case client := <-h.unregister:
			h.mu.Lock()
			if _, ok := h.clients[client]; ok {
				delete(h.clients, client)
				close(client.send)
			}
			h.mu.Unlock()
			slog.Info("stats ws client disconnected", "total", h.clientCount())

		case <-ticker.C:
			h.broadcast()
		}
	}
}

func (h *StatsHub) broadcast() {
	payload := Collect()
	data, err := json.Marshal(payload)
	if err != nil {
		slog.Error("stats marshal failed", "error", err)
		return
	}

	h.mu.RLock()
	defer h.mu.RUnlock()

	for client := range h.clients {
		select {
		case client.send <- data:
		default:
			// slow client, drop message
		}
	}
}

func (h *StatsHub) clientCount() int {
	// caller must hold lock or accept race (used only for logging)
	return len(h.clients)
}

func (h *StatsHub) HandleWS(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		slog.Error("stats ws upgrade failed", "error", err)
		return
	}

	client := &statsClient{
		hub:  h,
		conn: conn,
		send: make(chan []byte, 16),
	}

	h.register <- client

	// Send immediate stats snapshot on connect
	snapshot, _ := json.Marshal(Collect())
	client.send <- snapshot

	go client.writePump()
	go client.readPump()
}

func (c *statsClient) readPump() {
	defer func() {
		c.hub.unregister <- c
		c.conn.Close()
	}()

	c.conn.SetReadDeadline(time.Now().Add(120 * time.Second))
	c.conn.SetPongHandler(func(string) error {
		c.conn.SetReadDeadline(time.Now().Add(120 * time.Second))
		return nil
	})

	for {
		_, _, err := c.conn.ReadMessage()
		if err != nil {
			break
		}
	}
}

func (c *statsClient) writePump() {
	ticker := time.NewTicker(30 * time.Second)
	defer func() {
		ticker.Stop()
		c.conn.Close()
	}()

	for {
		select {
		case msg, ok := <-c.send:
			c.conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			if !ok {
				c.conn.WriteMessage(websocket.CloseMessage, []byte{})
				return
			}
			if err := c.conn.WriteMessage(websocket.TextMessage, msg); err != nil {
				return
			}
		case <-ticker.C:
			c.conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			if err := c.conn.WriteMessage(websocket.PingMessage, nil); err != nil {
				return
			}
		}
	}
}
