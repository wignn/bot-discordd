package infoway

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"math/rand"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

type Client struct {
	apiKey   string
	business string
	symbols  string
	trades   chan TradeData
	mu       sync.Mutex
	conn     *websocket.Conn
}

func NewClient(apiKey, business, symbols string) *Client {
	return &Client{
		apiKey:   apiKey,
		business: business,
		symbols:  symbols,
		trades:   make(chan TradeData, 512),
	}
}

func (c *Client) Trades() <-chan TradeData {
	return c.trades
}

func (c *Client) Business() string {
	return c.business
}

func (c *Client) Run(ctx context.Context) {
	backoff := time.Second

	for {
		select {
		case <-ctx.Done():
			slog.Info("infoway client shutting down", "business", c.business)
			return
		default:
		}

		err := c.connect(ctx)
		if err != nil {
			slog.Error("infoway connection failed",
				"business", c.business,
				"error", err,
				"retry_in", backoff,
			)

			select {
			case <-ctx.Done():
				return
			case <-time.After(backoff):
			}

			backoff = min(backoff*2, 30*time.Second)
			continue
		}

		backoff = time.Second
		c.readLoop(ctx)
	}
}

func (c *Client) connect(ctx context.Context) error {
	url := fmt.Sprintf("wss://data.infoway.io/ws?business=%s&apikey=%s", c.business, c.apiKey)

	dialer := websocket.DefaultDialer
	dialer.HandshakeTimeout = 15 * time.Second

	conn, _, err := dialer.DialContext(ctx, url, nil)
	if err != nil {
		return fmt.Errorf("dial: %w", err)
	}

	c.mu.Lock()
	c.conn = conn
	c.mu.Unlock()

	slog.Info("infoway connected", "business", c.business)

	if err := c.subscribe(); err != nil {
		conn.Close()
		return fmt.Errorf("subscribe: %w", err)
	}

	go c.heartbeatLoop(ctx)

	return nil
}

func (c *Client) subscribe() error {
	req := SubscribeRequest{
		Code:  CodeSubscribeTrade,
		Trace: newTrace(),
		Data: map[string]interface{}{
			"codes": c.symbols,
		},
	}

	data, err := json.Marshal(req)
	if err != nil {
		return err
	}

	c.mu.Lock()
	defer c.mu.Unlock()

	if err := c.conn.WriteMessage(websocket.TextMessage, data); err != nil {
		return err
	}

	slog.Info("infoway subscribed",
		"business", c.business,
		"symbols", c.symbols,
	)

	return nil
}

func (c *Client) heartbeatLoop(ctx context.Context) {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			hb := HeartbeatRequest{
				Code:  CodeHeartbeat,
				Trace: newTrace(),
			}

			data, _ := json.Marshal(hb)

			c.mu.Lock()
			err := c.conn.WriteMessage(websocket.TextMessage, data)
			c.mu.Unlock()

			if err != nil {
				slog.Warn("infoway heartbeat failed",
					"business", c.business,
					"error", err,
				)
				return
			}

			slog.Debug("infoway heartbeat sent", "business", c.business)
		}
	}
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

		conn.SetReadDeadline(time.Now().Add(90 * time.Second))
		_, raw, err := conn.ReadMessage()
		if err != nil {
			slog.Warn("infoway read error",
				"business", c.business,
				"error", err,
			)
			return
		}

		var msg Message
		if err := json.Unmarshal(raw, &msg); err != nil {
			slog.Debug("infoway unmarshal error", "error", err, "raw", string(raw))
			continue
		}

		switch msg.Code {
		case CodeSubscribeResponse:
			slog.Info("infoway subscribe response",
				"business", c.business,
				"msg", msg.Msg,
			)

		case CodeTradePush:
			var trade TradeData
			if err := json.Unmarshal(msg.Data, &trade); err != nil {
				slog.Debug("infoway trade unmarshal error", "error", err)
				continue
			}

			select {
			case c.trades <- trade:
			default:
				slog.Debug("infoway trade channel full, dropping",
					"symbol", trade.Symbol,
				)
			}

		default:
			slog.Debug("infoway unknown code",
				"code", msg.Code,
				"raw", string(raw),
			)
		}
	}
}

func newTrace() string {
	return fmt.Sprintf("%016x%016x", rand.Int63(), rand.Int63())
}

func min(a, b time.Duration) time.Duration {
	if a < b {
		return a
	}
	return b
}
