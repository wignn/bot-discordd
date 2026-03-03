import sys
try:
    import MetaTrader5 as mt5
    if not mt5.initialize():
        print("[test] MT5 initialize failed:", mt5.last_error())
        sys.exit(1)
    info = mt5.terminal_info()
    print(f"[test] MT5 connected — build {info.build}, {info.name}")
    mt5.shutdown()
except Exception as e:
    print(f"[test] Error: {e}")
    sys.exit(1)
