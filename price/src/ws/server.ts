import { createServer } from "http";
import { WebSocketServer, WebSocket } from "ws";
import * as broadcaster from "./broadcaster";
import * as log from "../logger";

const TAG = "WS-SERVER";

let httpServer: ReturnType<typeof createServer> | null = null;
let wss: WebSocketServer | null = null;

export function start(port: number, heartbeatMs: number) {
  httpServer = createServer((req, res) => {
    if (req.url === "/health") {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ status: "ok", clients: broadcaster.clientCount() }));
      return;
    }
    res.writeHead(200);
    res.end("WebSocket server");
  });

  wss = new WebSocketServer({ server: httpServer });

  wss.on("connection", (ws) => {
    broadcaster.addClient(ws);

    ws.on("close", () => {
      broadcaster.removeClient(ws);
    });

    ws.on("error", () => {
      broadcaster.removeClient(ws);
    });
  });

  httpServer.listen(port, () => {
    log.info(TAG, `listening on port ${port}`);
  });

  setInterval(() => {
    broadcaster.broadcast(JSON.stringify({ event: "heartbeat" }));
  }, heartbeatMs);
}

export function stop() {
  if (wss) {
    wss.close();
  }
  if (httpServer) {
    httpServer.close();
  }
  log.info(TAG, "stopped");
}
