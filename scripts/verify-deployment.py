#!/usr/bin/env python3
"""
Deployment Verification Script

Checks if the deployed application is working correctly by:
1. Testing health endpoints
2. Verifying database connectivity
3. Testing basic API functionality
4. Checking ingestion and cleanup endpoints

Usage: python scripts/verify-deployment.py [URL]
"""

import argparse
import sys
from typing import Any, Dict

import requests


def check_endpoint(
    url: str, endpoint: str, expected_status: int = 200
) -> Dict[str, Any]:
    """Check a specific endpoint and return results."""
    full_url = f"{url.rstrip('/')}/{endpoint.lstrip('/')}"

    try:
        response = requests.get(full_url, timeout=30)

        result = {
            "endpoint": endpoint,
            "url": full_url,
            "status_code": response.status_code,
            "success": response.status_code == expected_status,
            "response_time": response.elapsed.total_seconds(),
        }

        # Try to parse JSON response
        try:
            result["response_data"] = response.json()
        except Exception:
            result["response_data"] = response.text[:200]

        return result

    except requests.exceptions.RequestException as e:
        return {
            "endpoint": endpoint,
            "url": full_url,
            "success": False,
            "error": str(e),
        }


def verify_deployment(base_url: str) -> bool:
    """Verify the deployment by checking multiple endpoints."""
    print(f"🔍 Verifying deployment at: {base_url}")
    print("=" * 50)

    # Define endpoints to check
    endpoints = [
        {"path": "/health", "name": "Health Check"},
        {"path": "/ready", "name": "Readiness Check"},
        {"path": "/", "name": "Root Endpoint"},
        {"path": "/sources", "name": "Sources API"},
        {"path": "/articles", "name": "Articles API"},
    ]

    all_passed = True
    results = []

    for endpoint in endpoints:
        print(f"Testing {endpoint['name']}...")
        result = check_endpoint(base_url, endpoint["path"])
        results.append(result)

        if result["success"]:
            print(f"✅ {endpoint['name']}: OK ({result.get('response_time', 0):.2f}s)")
            if "response_data" in result and isinstance(result["response_data"], dict):
                if "status" in result["response_data"]:
                    print(f"   Status: {result['response_data']['status']}")
        else:
            print(f"❌ {endpoint['name']}: FAILED")
            if "error" in result:
                print(f"   Error: {result['error']}")
            else:
                print(f"   Status Code: {result['status_code']}")
            all_passed = False

    # Test trigger endpoints (these might return 200 even if no work to do)
    print("\nTesting trigger endpoints...")
    trigger_endpoints = [
        {"path": "/trigger/ingestion", "name": "Ingestion Trigger"},
        {"path": "/trigger/cleanup", "name": "Cleanup Trigger"},
    ]

    for endpoint in trigger_endpoints:
        print(f"Testing {endpoint['name']}...")
        result = check_endpoint(base_url, endpoint["path"])

        if result["success"]:
            print(f"✅ {endpoint['name']}: OK ({result.get('response_time', 0):.2f}s)")
            if "response_data" in result:
                try:
                    data = result["response_data"]
                    if isinstance(data, dict) and "message" in data:
                        print(f"   Message: {data['message']}")
                except Exception:
                    pass
        else:
            print(f"⚠️  {endpoint['name']}: {result.get('status_code', 'ERROR')}")
            # Trigger endpoints failing is not critical for basic deployment

    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 Deployment verification PASSED!")
        print("✅ All critical endpoints are working")
        return True
    else:
        print("❌ Deployment verification FAILED!")
        print("🔧 Some critical endpoints are not working")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify deployment health")
    parser.add_argument(
        "url",
        nargs="?",
        default="https://aifeelnews-web-539765220780.us-central1.run.app",
        help="Base URL of the deployed application",
    )

    args = parser.parse_args()

    success = verify_deployment(args.url)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
