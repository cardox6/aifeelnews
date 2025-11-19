#!/usr/bin/env python3
"""
Quick test script to verify API endpoints are working
Run this to manually test the FastAPI server and endpoints
"""
import json
import os
import subprocess
import sys
import threading
import time

import requests

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def start_server():
    """Start the FastAPI server in background"""
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd()

    # Start server
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8002",
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait a bit for server to start
    time.sleep(3)
    return proc


def test_endpoints():
    """Test key API endpoints"""
    base_url = "http://127.0.0.1:8002"

    try:
        print("Testing API endpoints...")

        # Test root endpoint
        print("1. Testing root endpoint...")
        response = requests.get(f"{base_url}/", timeout=5)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")

        # Test articles endpoint
        print("\n2. Testing articles endpoint...")
        response = requests.get(f"{base_url}/articles?limit=3", timeout=5)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Found {len(data)} articles")
            if data:
                print(f"   Sample article: {data[0].get('title', 'No title')}")
        else:
            print(f"   Error: {response.text}")

        # Test sources endpoint
        print("\n3. Testing sources endpoint...")
        response = requests.get(f"{base_url}/sources?limit=5", timeout=5)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Found {len(data)} sources")
            if data:
                print(f"   Sample source: {data[0].get('name', 'No name')}")
        else:
            print(f"   Error: {response.text}")

        print("\n✅ API testing completed successfully!")
        return True

    except Exception as e:
        print(f"\n❌ Error testing API: {e}")
        return False


if __name__ == "__main__":
    print("Starting API server for testing...")
    server_proc = start_server()

    try:
        success = test_endpoints()
        if success:
            print("\n🎉 All API tests passed!")
        else:
            print("\n⚠️  Some API tests failed")
    finally:
        print("\nShutting down server...")
        server_proc.terminate()
        server_proc.wait()
