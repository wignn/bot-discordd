const DEFAULT_SYMBOLS = [
  "FX:XAUUSD",
  "FX:EURUSD",
  "FX:GBPUSD",
  "FX:USDJPY",
  "BINANCE:BTCUSDT",
  "BINANCE:ETHUSDT",
  "BINANCE:SOLUSDT",
  "BINANCE:BNBUSDT",
];

export interface Config {
  port: number;
  symbols: string[];
  logLevel: string;
  heartbeatInterval: number;
}

export function loadConfig(): Config {
  const raw = process.env.SYMBOLS || "";
  const symbols = raw
    ? raw.split(",").map((s: string) => s.trim()).filter(Boolean)
    : DEFAULT_SYMBOLS;

  return {
    port: parseInt(process.env.PORT || "4000", 10),
    symbols,
    logLevel: process.env.LOG_LEVEL || "info",
    heartbeatInterval: parseInt(process.env.HEARTBEAT_INTERVAL || "30000", 10),
  };
}
