package infoway

import "encoding/json"

type Message struct {
	Code  int             `json:"code"`
	Trace string          `json:"trace,omitempty"`
	Msg   string          `json:"msg,omitempty"`
	Data  json.RawMessage `json:"data,omitempty"`
}

type TradeData struct {
	Symbol    string `json:"s"`
	Price     string `json:"p"`
	Timestamp int64  `json:"t"`
	Direction int    `json:"td"`
	Volume    string `json:"v"`
	Value     string `json:"vw"`
}

type SubscribeRequest struct {
	Code  int                    `json:"code"`
	Trace string                 `json:"trace"`
	Data  map[string]interface{} `json:"data"`
}

type HeartbeatRequest struct {
	Code  int    `json:"code"`
	Trace string `json:"trace"`
}

const (
	CodeSubscribeTrade    = 10000
	CodeSubscribeResponse = 10001
	CodeTradePush         = 10002
	CodeSubscribeDepth    = 10003
	CodeSubscribeKline    = 10006
	CodeHeartbeat         = 10010
)

const (
	BusinessStock  = "stock"
	BusinessCrypto = "crypto"
	BusinessCommon = "common"
)

const (
	DirectionDefault = 0
	DirectionBuy     = 1
	DirectionSell    = 2
)
