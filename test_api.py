#!/usr/bin/env python3
"""
Test script for News Server API endpoints.

Usage:
    python test_api.py              # Run all tests
    python test_api.py news         # Test news endpoints
    python test_api.py stock        # Test stock endpoints
    python test_api.py ws           # Test WebSocket connection
    python test_api.py redis        # Test Redis stream
"""

import requests
import json
import sys
import time
import threading

BASE_URL = "http://localhost:8000"
API_KEY = ""  # Set if required

def get_headers():
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    return headers

def print_response(r, max_items=5):
    """Pretty print response with truncation for large lists"""
    try:
        data = r.json()
        if isinstance(data.get("items"), list) and len(data["items"]) > max_items:
            truncated = data.copy()
            truncated["items"] = data["items"][:max_items]
            truncated["_note"] = f"Showing {max_items} of {len(data['items'])} items"
            print(json.dumps(truncated, indent=2, default=str))
        else:
            print(json.dumps(data, indent=2, default=str))
    except:
        print(r.text[:500])



def test_health():
    """Test health check endpoint"""
    print("\n=== GET /health ===")
    try:
        r = requests.get(f"{BASE_URL}/health", headers=get_headers())
        print(f"Status: {r.status_code}")
        print_response(r)
        return r.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_root():
    """Test root endpoint"""
    print("\n=== GET / ===")
    try:
        r = requests.get(f"{BASE_URL}/", headers=get_headers())
        print(f"Status: {r.status_code}")
        print_response(r)
        return r.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False



def test_news_list():
    """Test news list with pagination"""
    print("\n=== GET /api/v1/news ===")
    try:
        r = requests.get(f"{BASE_URL}/api/v1/news?page=1&page_size=5", headers=get_headers())
        print(f"Status: {r.status_code}")
        print_response(r)
        return r.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_news_latest():
    """Test latest news endpoint"""
    print("\n=== GET /api/v1/news/latest ===")
    try:
        r = requests.get(f"{BASE_URL}/api/v1/news/latest?limit=5", headers=get_headers())
        print(f"Status: {r.status_code}")
        print_response(r)
        return r.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_news_by_id():
    """Test get news by ID"""
    print("\n=== GET /api/v1/news/{id} ===")
    try:
        # First get a news item to get its ID
        r = requests.get(f"{BASE_URL}/api/v1/news/latest?limit=1", headers=get_headers())
        if r.status_code != 200:
            print("Could not fetch news list")
            return False
        
        data = r.json()
        items = data.get("items", [])
        if not items:
            print("No news items found, skipping...")
            return True  # Not a failure, just no data
        
        news_id = items[0]["id"]
        print(f"Fetching news ID: {news_id}")
        
        r = requests.get(f"{BASE_URL}/api/v1/news/{news_id}", headers=get_headers())
        print(f"Status: {r.status_code}")
        print_response(r)
        return r.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False



def test_stock_latest():
    """Test latest stock news endpoint"""
    print("\n=== GET /api/v1/stock/latest ===")
    try:
        r = requests.get(f"{BASE_URL}/api/v1/stock/latest?limit=5", headers=get_headers())
        print(f"Status: {r.status_code}")
        print_response(r)
        return r.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False


def test_websocket():
    """Test WebSocket connection"""
    print("\n=== WebSocket Connection Test ===")
    try:
        import websocket
    except ImportError:
        print("websocket-client not installed. Run: pip install websocket-client")
        return False
    
    ws_url = BASE_URL.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{ws_url}/api/v1/stream/ws?channel=news"
    
    received_messages = []
    connected = threading.Event()
    
    def on_open(ws):
        print(f"Connected to: {ws_url}")
        connected.set()
    
    def on_message(ws, message):
        print(f"Received: {message[:200]}...")
        received_messages.append(message)
    
    def on_error(ws, error):
        print(f"WebSocket error: {error}")
    
    def on_close(ws, close_code, close_msg):
        print(f"WebSocket closed: {close_code} {close_msg}")
    
    try:
        ws = websocket.WebSocketApp(
            ws_url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )
        
        # Run WebSocket in background thread
        ws_thread = threading.Thread(target=ws.run_forever)
        ws_thread.daemon = True
        ws_thread.start()
        
        # Wait for connection
        if connected.wait(timeout=5):
            print("WebSocket connected successfully!")
            time.sleep(2)  # Wait for any initial messages
            ws.close()
            return True
        else:
            print("WebSocket connection timeout")
            return False
            
    except Exception as e:
        print(f"Error: {e}")
        return False


# ===== Redis Stream Test =====

def test_redis_stream():
    """Test Redis stream directly"""
    print("\n=== Redis Stream Test ===")
    try:
        import redis
    except ImportError:
        print("redis not installed. Run: pip install redis")
        return False
    
    try:
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
        r.ping()
        print("Redis connected!")
        
        # Check stream info
        streams = ["events.news", "events.stock", "events.calendar"]
        for stream in streams:
            try:
                info = r.xinfo_stream(stream)
                print(f"\n{stream}:")
                print(f"  Length: {info['length']}")
                print(f"  First entry: {info.get('first-entry', 'N/A')}")
                print(f"  Last entry: {info.get('last-entry', 'N/A')}")
                
                # Check consumer groups
                groups = r.xinfo_groups(stream)
                for g in groups:
                    print(f"  Group '{g['name']}': {g['pending']} pending, {g['consumers']} consumers")
            except redis.ResponseError as e:
                if "no such key" in str(e).lower():
                    print(f"\n{stream}: (not created yet)")
                else:
                    print(f"\n{stream}: Error - {e}")
        
        return True
    except redis.ConnectionError:
        print("Could not connect to Redis at localhost:6379")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False

def run_all_tests():
    """Run all API tests"""
    print("=" * 60)
    print("News Server API Test Suite")
    print("=" * 60)
    
    results = []
    
    # Basic
    results.append(("Health Check", test_health()))
    results.append(("Root Endpoint", test_root()))
    
    # News
    results.append(("News List", test_news_list()))
    results.append(("News Latest", test_news_latest()))
    results.append(("News By ID", test_news_by_id()))
    
    # Stock
    results.append(("Stock Latest", test_stock_latest()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Results")
    print("=" * 60)
    
    passed = 0
    failed = 0
    for name, result in results:
        status = "PASS" if result else "FAIL"
        symbol = "✓" if result else "✗"
        print(f"  {symbol} {name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\nTotal: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0

def run_news_tests():
    """Run only news-related tests"""
    print("=== News API Tests ===")
    test_news_list()
    test_news_latest()
    test_news_by_id()

def run_stock_tests():
    """Run only stock-related tests"""
    print("=== Stock API Tests ===")
    test_stock_latest()

def print_usage():
    print("""
News Server API Test Script

Usage:
    python test_api.py              Run all tests
    python test_api.py news         Test news endpoints only
    python test_api.py stock        Test stock endpoints only  
    python test_api.py ws           Test WebSocket connection
    python test_api.py redis        Test Redis streams
    python test_api.py health       Quick health check

Environment:
    BASE_URL: {BASE_URL}
""".format(BASE_URL=BASE_URL))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "news":
            run_news_tests()
        elif cmd == "stock":
            run_stock_tests()
        elif cmd == "ws":
            test_websocket()
        elif cmd == "redis":
            test_redis_stream()
        elif cmd == "health":
            test_health()
        elif cmd in ["-h", "--help", "help"]:
            print_usage()
        else:
            print(f"Unknown command: {cmd}")
            print_usage()
    else:
        run_all_tests()
