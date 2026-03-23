import { WebSocket } from "ws";
import * as log from "../logger";
import * as priceCache from "../cache/price-cache";

const TAG = "BROADCASTER";

const clients = new Set<WebSocket>();

export function addClient(ws: WebSocket) {
  clients.add(ws);
  log.info(TAG, "client connected", { total: clients.size });
  sendSnapshot(ws);
}

export function removeClient(ws: WebSocket) {
  clients.delete(ws);
  log.info(TAG, "client disconnected", { total: clients.size });
}

export function broadcast(message: string) {
  for (const ws of clients) {
    if (ws.readyState === WebSocket.OPEN) {
      try {
        ws.send(message);
      } catch {
        clients.delete(ws);
      }
    }
  }
}

export function broadcastTrade(entry: priceCache.PriceEntry) {
  const payload = JSON.stringify(priceCache.toTradePayload(entry));
  broadcast(payload);
}

export function clientCount(): number {
  return clients.size;
}

function sendSnapshot(ws: WebSocket) {
  const all = priceCache.getAll();
  for (const entry of all) {
    if (ws.readyState !== WebSocket.OPEN) break;
    try {
      ws.send(JSON.stringify(priceCache.toTradePayload(entry)));
    } catch {
      break;
    }
  }
}
