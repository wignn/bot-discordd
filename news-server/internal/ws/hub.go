package ws

import (
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

type Client struct {
	hub      *Hub
	conn     *websocket.Conn
	send     chan []byte
	botID    string
	channels map[string]bool
}

type Hub struct {
	mu         sync.RWMutex
	clients    map[*Client]bool
	register   chan *Client
	unregister chan *Client
}

func NewHub() *Hub {
	return &Hub{
		clients:    make(map[*Client]bool),
		register:   make(chan *Client),
		unregister: make(chan *Client),
	}
}

func (h *Hub) Run() {
	for {
		select {
		case client := <-h.register:
			h.mu.Lock()
			h.clients[client] = true
			h.mu.Unlock()
			slog.Info("ws client connected", "bot_id", client.botID, "total", h.ClientCount())
		case client := <-h.unregister:
			h.mu.Lock()
			if _, ok := h.clients[client]; ok {
				delete(h.clients, client)
				close(client.send)
			}
			h.mu.Unlock()
			slog.Info("ws client disconnected", "bot_id", client.botID, "total", h.ClientCount())
		}
	}
}

func (h *Hub) ClientCount() int {
	h.mu.RLock()
	defer h.mu.RUnlock()
	return len(h.clients)
}

func (h *Hub) Broadcast(eventType string, data map[string]interface{}, channel string) int {
	msg := map[string]interface{}{
		"event":     eventType,
		"data":      data,
		"channel":   channel,
		"timestamp": time.Now().UTC().Format(time.RFC3339),
	}

	payload, err := json.Marshal(msg)
	if err != nil {
		slog.Error("failed to marshal broadcast", "error", err)
		return 0
	}

	h.mu.RLock()
	defer h.mu.RUnlock()

	count := 0
	for client := range h.clients {
		if client.channels["all"] || client.channels[channel] {
			select {
			case client.send <- payload:
				count++
			default:
				// client send buffer full, skip
			}
		}
	}

	slog.Info("broadcast sent", "event", eventType, "channel", channel, "clients", count)
	return count
}

func (h *Hub) HandleWS(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		slog.Error("ws upgrade failed", "error", err)
		return
	}

	botID := r.URL.Query().Get("bot_id")
	if botID == "" {
		botID = r.URL.Query().Get("client_type")
	}
	if botID == "" {
		botID = "unknown"
	}

	client := &Client{
		hub:   h,
		conn:  conn,
		send:  make(chan []byte, 256),
		botID: botID,
		channels: map[string]bool{
			"all":         true,
			"news":        true,
			"stock_news":  true,
			"high_impact": true,
			"calendar":    true,
			"system":      true,
		},
	}

	h.register <- client

	// Send connected event
	welcome, _ := json.Marshal(map[string]interface{}{
		"event": "connected",
		"data": map[string]interface{}{
			"message": "Connected to Forex News WebSocket",
			"bot_id":  botID,
		},
	})
	client.send <- welcome

	go client.writePump()
	go client.readPump()
}

func (c *Client) readPump() {
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

func (c *Client) writePump() {
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
