import { loadConfig } from "./config";
import { setLogLevel, info } from "./logger";
import * as priceCache from "./cache/price-cache";
import * as broadcaster from "./ws/broadcaster";
import * as wsServer from "./ws/server";
import * as tradingview from "./provider/tradingview";

const TAG = "MAIN";

const config = loadConfig();
setLogLevel(config.logLevel);

info(TAG, "starting price service", {
  port: config.port,
  symbols: config.symbols.length,
  logLevel: config.logLevel,
});

wsServer.start(config.port, config.heartbeatInterval);

tradingview.start(config.symbols, (tick) => {
  const entry = priceCache.update(
    tick.symbol,
    tick.price,
    tick.priceStr,
    tick.volume,
    tick.volumeStr,
    tick.assetType,
    tick.tradeTime,
  );
  broadcaster.broadcastTrade(entry);
});

function shutdown() {
  info(TAG, "shutting down");
  tradingview.stop();
  wsServer.stop();
  process.exit(0);
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
