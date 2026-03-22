import socket
import json
import time
import threading
import MetaTrader5 as mt5

HOST = "0.0.0.0"
PORT = 9999

mt5.initialize()
print(f"[tick_producer] MT5 initialized, listening on {HOST}:{PORT}")


def handle_client(conn, addr):
    print(f"[tick_producer] Client connected: {addr}")
    try:
        data = b""
        while b"\n" not in data:
            chunk = conn.recv(1024)
            if not chunk:
                return
            data += chunk

        symbol = data.decode().strip()
        print(f"[tick_producer] Streaming ticks for: {symbol}")

        if not mt5.symbol_select(symbol, True):
            error = json.dumps({"error": f"Symbol '{symbol}' not available"}) + "\n"
            conn.sendall(error.encode())
            return

        # wait for symbol to load in Market Watch
        tick = None
        for _ in range(10):
            tick = mt5.symbol_info_tick(symbol)
            if tick is not None:
                break
            time.sleep(0.5)

        if tick is None:
            error = json.dumps({"error": f"Symbol '{symbol}' not found (timeout waiting for tick data)"}) + "\n"
            conn.sendall(error.encode())
            return

        last_tick_time = 0
        while True:
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                break
            
            if tick.time_msc != last_tick_time:
                last_tick_time = tick.time_msc
                payload = json.dumps({
                    "symbol": symbol,
                    "bid": tick.bid,
                    "ask": tick.ask,
                    "spread": round((tick.ask - tick.bid) * 100, 2),
                    "last": tick.last,
                    "volume": float(tick.volume),
                    "time": tick.time,
                    "time_msc": tick.time_msc,
                }) + "\n"
                conn.sendall(payload.encode())

            time.sleep(0.2)  # poll every 200ms

    except (ConnectionResetError, BrokenPipeError, OSError):
        print(f"[tick_producer] Client {addr} disconnected")
    finally:
        conn.close()


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(10)

    while True:
        conn, addr = server.accept()
        t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        t.start()


if __name__ == "__main__":
    main()
