#!/usr/bin/env python3
"""Simple test script for News API endpoints"""

import requests
import json

BASE_URL = "http://localhost:8000"

def test_health():
    print("\n=== Health Check ===")
    try:
        r = requests.get(f"{BASE_URL}/health")
        print(f"Status: {r.status_code}")
        print(f"Response: {r.json()}")
        return r.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_root():
    print("\n=== Root ===")
    try:
        r = requests.get(f"{BASE_URL}/")
        print(f"Status: {r.status_code}")
        print(f"Response: {r.json()}")
        return r.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_ws_stats():
    """Test WebSocket stats endpoint"""
    print("\n=== WebSocket Stats ===")
    try:
        r = requests.get(f"{BASE_URL}/api/v1/stream/ws/stats")
        print(f"Status: {r.status_code}")
        print(f"Response: {json.dumps(r.json(), indent=2)}")
        return r.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_ws_clients():
    print("\n=== WebSocket Clients ===")
    try:
        r = requests.get(f"{BASE_URL}/api/v1/stream/ws/clients")
        print(f"Status: {r.status_code}")
        print(f"Response: {json.dumps(r.json(), indent=2)}")
        return r.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_broadcast_news():
    print("\n=== Broadcast Test News ===")
    try:
        r = requests.post(f"{BASE_URL}/api/v1/stream/ws/test-news")
        print(f"Status: {r.status_code}")
        print(f"Response: {json.dumps(r.json(), indent=2)}")
        return r.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_broadcast_high_impact():
    """Test broadcast high impact alert"""
    print("\n=== Broadcast High Impact Alert ===")
    try:
        r = requests.post(f"{BASE_URL}/api/v1/stream/ws/test-high-impact")
        print(f"Status: {r.status_code}")
        print(f"Response: {json.dumps(r.json(), indent=2)}")
        return r.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def main():
    print("=" * 50)
    print("News API Test Script")
    print("=" * 50)
    
    results = []
    
    results.append(("Health", test_health()))
    results.append(("Root", test_root()))
    results.append(("WS Stats", test_ws_stats()))
    results.append(("WS Clients", test_ws_clients()))
    
    print("\n" + "=" * 50)
    print("Summary")
    print("=" * 50)
    
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {name}: {status}")
    
    print("\n" + "=" * 50)
    print("Manual Tests (run separately):")
    print("  python test_api.py broadcast    - Send test news")
    print("  python test_api.py alert        - Send high impact alert")
    print("=" * 50)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "broadcast":
            test_broadcast_news()
        elif cmd == "alert":
            test_broadcast_high_impact()
        else:
            print(f"Unknown command: {cmd}")
    else:
        main()
