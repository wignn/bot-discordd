import socket, sys

host = "localhost"
port = 8001

s = socket.socket()
s.settimeout(5)
try:
    s.connect((host, port))
    print(f"TCP connected to {host}:{port}")
    data = s.recv(256)
    print(f"Received {len(data)} bytes: {repr(data[:80])}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
finally:
    s.close()
