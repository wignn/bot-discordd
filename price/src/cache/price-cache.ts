export interface PriceEntry {
  symbol: string;
  price: number;
  priceStr: string;
  volume: number;
  volumeStr: string;
  direction: string;
  assetType: string;
  tradeTime: string;
}

const cache = new Map<string, PriceEntry>();

export function update(
  symbol: string,
  price: number,
  priceStr: string,
  volume: number,
  volumeStr: string,
  assetType: string,
  tradeTime: string,
): PriceEntry {
  const prev = cache.get(symbol);
  let direction = "neutral";
  if (prev) {
    if (price > prev.price) direction = "buy";
    else if (price < prev.price) direction = "sell";
  }

  const entry: PriceEntry = {
    symbol,
    price,
    priceStr,
    volume,
    volumeStr,
    direction,
    assetType,
    tradeTime,
  };

  cache.set(symbol, entry);
  return entry;
}

export function get(symbol: string): PriceEntry | undefined {
  return cache.get(symbol);
}

export function getAll(): PriceEntry[] {
  return Array.from(cache.values());
}

export function toTradePayload(entry: PriceEntry) {
  return {
    event: "market.trade",
    data: {
      symbol: entry.symbol,
      price: entry.price,
      price_str: entry.priceStr,
      volume: entry.volume,
      volume_str: entry.volumeStr,
      direction: entry.direction,
      asset_type: entry.assetType,
      trade_time: entry.tradeTime,
    },
  };
}
