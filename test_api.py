import json
import sys
import time
import threading
import requests

BASE_URL = "http://localhost:8000"
API_KEY = ""

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def get_headers():
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    return headers

def pretty_print(data, max_items=5):
    try:
        response_data = data.json()
        
        if isinstance(response_data.get("items"), list):
            total = len(response_data["items"])
            if total > max_items:
                truncated = response_data.copy()
                truncated["items"] = response_data["items"][:max_items]
                truncated["_truncated"] = f"Showing {max_items}/{total} items"
                print(json.dumps(truncated, indent=2, default=str))
                return
        
        print(json.dumps(response_data, indent=2, default=str))
    except (ValueError, AttributeError):
        print(data.text[:500])

def test_endpoint(name, func):
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}{name}{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}")
    
    try:
        return func()
    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.END}")
        return False

def check_health():
    r = requests.get(f"{BASE_URL}/health", headers=get_headers())
    print(f"Status: {r.status_code}")
    pretty_print(r)
    return r.status_code == 200

def check_root():
    r = requests.get(f"{BASE_URL}/", headers=get_headers())
    print(f"Status: {r.status_code}")
    pretty_print(r)
    return r.status_code == 200

def test_news_list():
    r = requests.get(
        f"{BASE_URL}/api/v1/news",
        params={"page": 1, "page_size": 5},
        headers=get_headers()
    )
    print(f"Status: {r.status_code}")
    pretty_print(r)
    return r.status_code == 200

def test_news_latest():
    r = requests.get(
        f"{BASE_URL}/api/v1/news/latest",
        params={"limit": 5},
        headers=get_headers()
    )
    print(f"Status: {r.status_code}")
    pretty_print(r)
    return r.status_code == 200

def test_news_by_id():
    r = requests.get(
        f"{BASE_URL}/api/v1/news/latest",
        params={"limit": 1},
        headers=get_headers()
    )
    
    if r.status_code != 200:
        print("Failed to fetch news list")
        return False
    
    items = r.json().get("items", [])
    if not items:
        print("No news items available (skipped)")
        return True
    
    news_id = items[0]["id"]
    print(f"Testing with news ID: {news_id}")
    
    r = requests.get(f"{BASE_URL}/api/v1/news/{news_id}", headers=get_headers())
    print(f"Status: {r.status_code}")
    pretty_print(r)
    return r.status_code == 200

def test_stock_latest():
    r = requests.get(
        f"{BASE_URL}/api/v1/stock/latest",
        params={"limit": 5},
        headers=get_headers()
    )
    print(f"Status: {r.status_code}")
    pretty_print(r)
    return r.status_code == 200

def test_websocket():
    try:
        import websocket
    except ImportError:
        print(f"{Colors.YELLOW}Missing dependency: pip install websocket-client{Colors.END}")
        return False
    
    ws_url = BASE_URL.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{ws_url}/api/v1/stream/ws?channel=news"
    
    messages = []
    connected = threading.Event()
    
    def on_open(ws):
        print(f"{Colors.GREEN}Connected to: {ws_url}{Colors.END}")
        connected.set()
    
    def on_message(ws, msg):
        print(f"Received: {msg[:150]}...")
        messages.append(msg)
    
    def on_error(ws, error):
        print(f"{Colors.RED}Error: {error}{Colors.END}")
    
    def on_close(ws, code, msg):
        print(f"Closed: {code} - {msg}")
    
    ws = websocket.WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    
    ws_thread = threading.Thread(target=ws.run_forever, daemon=True)
    ws_thread.start()
    
    if connected.wait(timeout=5):
        time.sleep(2)
        ws.close()
        print(f"{Colors.GREEN}WebSocket test passed{Colors.END}")
        return True
    
    print(f"{Colors.RED}Connection timeout{Colors.END}")
    return False

def run_full_suite():
    print(f"\n{Colors.BLUE}{'='*60}")
    print("News Server API Test Suite")
    print(f"{'='*60}{Colors.END}\n")
    
    tests = [
        ("Health Check", check_health),
        ("Root Endpoint", check_root),
        ("News List", test_news_list),
        ("News Latest", test_news_latest),
        ("News By ID", test_news_by_id),
        ("Stock Latest", test_stock_latest),
    ]
    
    results = [(name, test_endpoint(name, func)) for name, func in tests]
    
    print(f"\n{Colors.BLUE}{'='*60}")
    print("Summary")
    print(f"{'='*60}{Colors.END}\n")
    
    passed = sum(1 for _, result in results if result)
    failed = len(results) - passed
    
    for name, result in results:
        status = f"{Colors.GREEN}✓ PASS{Colors.END}" if result else f"{Colors.RED}✗ FAIL{Colors.END}"
        print(f"  {status} {name}")
    
    print(f"\n{Colors.BLUE}Total: {passed} passed, {failed} failed{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}\n")
    
    return failed == 0

def run_news_suite():
    test_endpoint("News List", test_news_list)
    test_endpoint("News Latest", test_news_latest)
    test_endpoint("News By ID", test_news_by_id)

def run_stock_suite():
    test_endpoint("Stock Latest", test_stock_latest)

def print_help():
    print(__doc__)
    print(f"Current BASE_URL: {BASE_URL}\n")

def main():
    if len(sys.argv) < 2:
        run_full_suite()
        return
    
    command = sys.argv[1].lower()
    
    commands = {
        "news": run_news_suite,
        "stock": run_stock_suite,
        "ws": lambda: test_endpoint("WebSocket", test_websocket),
        "health": lambda: test_endpoint("Health Check", check_health),
        "help": print_help,
        "-h": print_help,
        "--help": print_help,
    }
    
    handler = commands.get(command)
    if handler:
        handler()
    else:
        print(f"{Colors.RED}Unknown command: {command}{Colors.END}\n")
        print_help()

if __name__ == "__main__":
    main()