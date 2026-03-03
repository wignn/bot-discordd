package mt5

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

// Tick represents a single price tick from the MT5 WebSocket server.
type Tick struct {
	Symbol  string  `json:"symbol"`
	Bid     float64 `json:"bid"`
	Ask     float64 `json:"ask"`
	Spread  float64 `json:"spread"`
	Last    float64 `json:"last"`
	Volume  float64 `json:"volume"`
	Time    int64   `json:"time"`
	TimeMsc int64   `json:"time_msc"`
	Error   string  `json:"error,omitempty"`
}

// Client manages a WebSocket connection to the MT5Docker tick server
// for a single symbol.
type Client struct {
	wsURL  string
	symbol string
	ticks  chan Tick
	mu     sync.Mutex
	conn   *websocket.Conn
}

// NewClient creates a new MT5 WebSocket client for the given symbol.
func NewClient(wsURL, symbol string) *Client {
	return &Client{
		wsURL:  wsURL,
		symbol: symbol,
		ticks:  make(chan Tick, 256),
	}
}

// Ticks returns a read-only channel of incoming ticks.
func (c *Client) Ticks() <-chan Tick {
	return c.ticks
}

// Symbol returns the MT5 symbol name this client is subscribed to.
func (c *Client) Symbol() string {
	return c.symbol
}

// Run connects to the MT5 WebSocket server and streams ticks until the
// context is cancelled. It reconnects automatically on failure.
func (c *Client) Run(ctx context.Context) {
	backoff := time.Second

	for {
		select {
		case <-ctx.Done():
			slog.Info("mt5 client shutting down", "symbol", c.symbol)
			return
		default:
		}

		err := c.connect(ctx)
		if err != nil {
			slog.Error("mt5 connection failed",
				"symbol", c.symbol,
				"error", err,
				"retry_in", backoff,
			)

			select {
			case <-ctx.Done():
				return
			case <-time.After(backoff):
			}

			if backoff < 30*time.Second {
				backoff *= 2
			}
			continue
		}

		backoff = time.Second
		c.readLoop(ctx)
	}
}

func (c *Client) connect(ctx context.Context) error {
	dialer := websocket.DefaultDialer
	dialer.HandshakeTimeout = 15 * time.Second

	conn, _, err := dialer.DialContext(ctx, c.wsURL, nil)
	if err != nil {
		return fmt.Errorf("dial %s: %w", c.wsURL, err)
	}

	c.mu.Lock()
	c.conn = conn
	c.mu.Unlock()

	// Subscribe by sending the symbol name
	sub := map[string]string{"symbol": c.symbol}
	data, _ := json.Marshal(sub)
	if err := conn.WriteMessage(websocket.TextMessage, data); err != nil {
		conn.Close()
		return fmt.Errorf("subscribe %s: %w", c.symbol, err)
	}

	slog.Info("mt5 connected", "symbol", c.symbol, "url", c.wsURL)
	return nil
}

func (c *Client) readLoop(ctx context.Context) {
	defer func() {
		c.mu.Lock()
		if c.conn != nil {
			c.conn.Close()
		}
		c.mu.Unlock()
	}()

	for {
		select {
		case <-ctx.Done():
			return
		default:
		}

		c.mu.Lock()
		conn := c.conn
		c.mu.Unlock()

		if conn == nil {
			return
		}

		conn.SetReadDeadline(time.Now().Add(30 * time.Second))
		_, raw, err := conn.ReadMessage()
		if err != nil {
			slog.Warn("mt5 read error", "symbol", c.symbol, "error", err)
			return
		}

		var tick Tick
		if err := json.Unmarshal(raw, &tick); err != nil {
			slog.Debug("mt5 unmarshal error", "error", err, "raw", string(raw))
			continue
		}

		if tick.Error != "" {
			slog.Error("mt5 server error", "symbol", c.symbol, "error", tick.Error)
			continue
		}

		select {
		case c.ticks <- tick:
		default:
			slog.Debug("mt5 tick channel full, dropping", "symbol", c.symbol)
		}
	}
}
