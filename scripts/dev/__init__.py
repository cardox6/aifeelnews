#!/usr/bin/env python3
"""
Development Scripts Index for aiFeelNews

This directory contains utilities for development, debugging, and testing.
"""

import os
import sys
from pathlib import Path

def list_scripts():
    """List available development scripts with descriptions"""
    
    scripts = [
        {
            "name": "test_api.py",
            "description": "Manual API endpoint testing with live server",
            "usage": "python scripts/dev/test_api.py"
        },
        {
            "name": "check_articles.py", 
            "description": "Quick database inspection - shows recent articles with sentiment",
            "usage": "python scripts/dev/check_articles.py"
        }
    ]
    
    print("🔧 aiFeelNews Development Scripts")
    print("=" * 40)
    
    for script in scripts:
        print(f"\n📄 {script['name']}")
        print(f"   {script['description']}")
        print(f"   Usage: {script['usage']}")
    
    print(f"\n📁 Other utility scripts:")
    print(f"   scripts/discover_sources.py - Discover available Mediastack news sources")
    
    print(f"\n💡 Main application commands:")
    print(f"   python -m app.jobs.run_ingestion     # Fetch and process news")
    print(f"   python -m app.jobs.ttl_cleanup       # Clean up expired content")
    print(f"   uvicorn app.main:app --reload         # Start API server")
    print(f"   pytest                                # Run test suite")

if __name__ == "__main__":
    list_scripts()