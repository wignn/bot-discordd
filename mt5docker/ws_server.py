import asyncio
import json
import websockets

TICK_PRODUCER_HOST = "127.0.0.1"
TICK_PRODUCER_PORT = 9999
WS_HOST = "0.0.0.0"
WS_PORT = 8765


async def stream_ticks(websocket):
    writer = None
    try:
        msg = await websocket.recv()
        data = json.loads(msg)
        symbol = data.get("symbol", "XAUUSDm")
        print(f"[ws_server] Client subscribed to: {symbol}")

        reader, writer = await asyncio.open_connection(
            TICK_PRODUCER_HOST, TICK_PRODUCER_PORT
        )
        writer.write(f"{symbol}\n".encode())
        await writer.drain()

        while True:
            line = await reader.readline()
            if not line:
                break
            tick_json = line.decode().strip()
            await websocket.send(tick_json)

    except websockets.ConnectionClosed:
        print(f"[ws_server] Client disconnected")
    except ConnectionRefusedError:
        error = json.dumps({"error": "tick_producer not running on port 9999"})
        await websocket.send(error)
    except Exception as e:
        print(f"[ws_server] Error: {e}")
    finally:
        if writer:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass


async def main():
    print(f"[ws_server] WebSocket server starting on ws://{WS_HOST}:{WS_PORT}")
    async with websockets.serve(stream_ticks, WS_HOST, WS_PORT):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
