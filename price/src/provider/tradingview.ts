import TradingView from "@mathieuc/tradingview";
import * as log from "../logger";

const TAG = "TRADINGVIEW";

type TickCallback = (data: {
  symbol: string;
  price: number;
  priceStr: string;
  volume: number;
  volumeStr: string;
  assetType: string;
  tradeTime: string;
}) => void;

let client: any = null;
let onTick: TickCallback | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let activeSymbols: string[] = [];

function parseSymbol(raw: string): { market: string; symbol: string; cleanSymbol: string; assetType: string } {
  const parts = raw.split(":");
  const market = parts.length > 1 ? parts[0] : "FX";
  const symbol = parts.length > 1 ? parts[1] : parts[0];

  let assetType = "forex";
  const m = market.toUpperCase();
  if (m === "CRYPTO" || m === "BINANCE" || m === "COINBASE") {
    assetType = "crypto";
  } else if (m === "NYSE" || m === "NASDAQ" || m === "IDX") {
    assetType = "stock";
  }

  return { market, symbol, cleanSymbol: symbol.replace(/[^A-Z0-9]/gi, ""), assetType };
}

function formatPrice(price: number, assetType: string, symbol: string): string {
  if (assetType === "crypto") return price.toFixed(2);
  const upper = symbol.toUpperCase();
  if (upper.includes("JPY")) return price.toFixed(3);
  if (upper.includes("XAU") || upper.includes("GOLD")) return price.toFixed(2);
  return price.toFixed(5);
}

function connect(symbols: string[]) {
  try {
    if (client) {
      try { client.end(); } catch {}
    }

    client = new TradingView.Client();

    client.onConnected(() => {
      log.info(TAG, "connected to TradingView");
    });

    client.onDisconnected(() => {
      log.warn(TAG, "disconnected, reconnecting in 5s");
      client = null;
      scheduleReconnect(symbols);
    });

    client.onError((...args: any[]) => {
      log.error(TAG, "error", { detail: String(args[0] || "") });
    });

    for (const raw of symbols) {
      const { market, symbol, cleanSymbol, assetType } = parseSymbol(raw);
      const fullSymbol = `${market}:${symbol}`;

      const chart = new client.Session.Chart();

      chart.setMarket(fullSymbol, {
        timeframe: "1",
        range: 1,
      });

      chart.onUpdate(() => {
        if (!onTick || !chart.periods || !chart.periods[0]) return;

        const tick = chart.periods[0];
        const price = tick.close;
        const priceStr = formatPrice(price, assetType, cleanSymbol);
        const volume = tick.volume || 0;
        const volumeStr = volume.toFixed(2);
        const tradeTime = new Date(tick.time * 1000).toISOString();

        onTick({
          symbol: cleanSymbol,
          price,
          priceStr,
          volume,
          volumeStr,
          assetType,
          tradeTime,
        });
      });

      log.info(TAG, `subscribed to ${fullSymbol}`, { assetType });
    }
  } catch (err: any) {
    log.error(TAG, "connection setup failed", { error: err?.message || String(err) });
    scheduleReconnect(symbols);
  }
}

function scheduleReconnect(symbols: string[]) {
  if (reconnectTimer) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    log.info(TAG, "attempting reconnect");
    connect(symbols);
  }, 5000);
}

export function start(symbols: string[], callback: TickCallback) {
  onTick = callback;
  activeSymbols = symbols;
  connect(symbols);
}

export function stop() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  if (client) {
    try { client.end(); } catch {}
    client = null;
  }
  log.info(TAG, "stopped");
}
