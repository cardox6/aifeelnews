#!/usr/bin/env python3
"""
Development Scripts Index for aiFeelNews

This directory contains utilities for development, debugging, and testing.
"""


def list_scripts():
    """List available development scripts with descriptions"""

    scripts = [
        {
            "name": "test_api.py",
            "description": "Manual API endpoint testing with live server",
            "usage": "python scripts/dev/test_api.py",
        },
        {
            "name": "check_articles.py",
            "description": "Quick database inspection - shows recent articles with sentiment",
            "usage": "python scripts/dev/check_articles.py",
        },
        {
            "name": "set_admin_claim.py",
            "description": "Grant/revoke the role=admin Firebase custom claim for a user",
            "usage": "python scripts/dev/set_admin_claim.py user@example.com [--revoke]",
        },
    ]

    print("🔧 aiFeelNews Development Scripts")
    print("=" * 40)

    for script in scripts:
        print(f"\n📄 {script['name']}")
        print(f"   {script['description']}")
        print(f"   Usage: {script['usage']}")

    print("\n📁 Other utility scripts:")
    print("   scripts/discover_sources.py - Discover available Mediastack news sources")

    print("\n💡 Main application commands:")
    print("   python -m app.jobs.run_ingestion     # Fetch and process news")
    print("   python -m app.jobs.ttl_cleanup       # Clean up expired content")
    print("   uvicorn app.main:app --reload         # Start API server")
    print("   pytest                                # Run test suite")


if __name__ == "__main__":
    list_scripts()
