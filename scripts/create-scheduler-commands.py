#!/usr/bin/env python3
"""
Generate Cloud Scheduler commands for aiFeelNews
This script generates the gcloud commands to create Cloud Scheduler jobs
"""

import os
import sys

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import config  # noqa: E402


def main() -> None:
    """Generate Cloud Scheduler commands"""

    # Configuration from app
    service_url = "https://aifeelnews-web-813770885946.europe-west1.run.app"
    schedule = config.scheduler.ingestion_schedule
    region = "europe-west1"

    print("🚀 Cloud Scheduler Commands for aiFeelNews")
    print("=" * 60)
    print(f"Service URL: {service_url}")
    print(f"Schedule: {schedule} (UTC)")
    print(f"Region: {region}")
    print()

    print("📋 Commands to run:")
    print()

    # Ingestion job command
    ingestion_cmd = [
        "gcloud scheduler jobs create http aifeelnews-ingestion",
        f'--schedule="{schedule}"',
        "--time-zone=UTC",
        f"--uri={service_url}/api/v1/trigger-ingestion",
        "--http-method=POST",
        f"--location={region}",
        '--description="Automated news ingestion (every 8 hours, API optimized)"',
    ]

    print("1. Create ingestion job:")
    print(" \\\n  ".join(ingestion_cmd))
    print()

    # Cleanup job command
    cleanup_cmd = [
        "gcloud scheduler jobs create http aifeelnews-cleanup",
        '--schedule="0 2 * * *"',
        "--time-zone=UTC",
        f"--uri={service_url}/api/v1/cleanup",
        "--http-method=POST",
        f"--location={region}",
        '--description="Daily cleanup of expired content (2 AM UTC)"',
    ]

    print("2. Create cleanup job:")
    print(" \\\n  ".join(cleanup_cmd))
    print()

    print("📊 Expected Results:")
    print(f"- Daily articles: ~{config.scheduler.daily_articles_estimate:,}")
    print(f"- Monthly API requests: ~{config.scheduler.monthly_api_usage_estimate:,}")
    print(f"- API usage: {config.scheduler.api_usage_percentage:.1f}% of 10,000 limit")
    print()
    print("✅ Run these commands in your terminal to create the jobs!")


if __name__ == "__main__":
    main()
