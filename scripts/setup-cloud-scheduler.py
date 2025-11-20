#!/usr/bin/env python3
"""
Cloud Scheduler Setup Script

Creates optimized Cloud Scheduler jobs for aiFeelNews:
- Ingestion job: Every 8 hours (3x daily, ~4,500 articles/day)
- Uses 54% of 10,000 monthly API limit (safe buffer)
- Cleanup job: Daily at 2 AM UTC
"""

import subprocess
import sys
from typing import List

from app.config import config


def run_gcloud_command(cmd: List[str]) -> bool:
    """Execute a gcloud command and return success status."""
    try:
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"✅ Success: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e.stderr.strip()}")
        return False


def create_ingestion_job() -> bool:
    """Create the main ingestion job (every 8 hours)."""
    cmd = [
        "gcloud",
        "scheduler",
        "jobs",
        "create",
        "http",
        config.scheduler.ingestion_job_name,
        f"--schedule={config.scheduler.ingestion_schedule}",
        f"--time-zone={config.scheduler.ingestion_timezone}",
        f"--uri={config.scheduler.trigger_url}",
        "--http-method=POST",
        f"--location={config.scheduler.scheduler_region}",
        "--description=Automated news ingestion (every 8 hours, optimized for API limits)",
    ]
    return run_gcloud_command(cmd)


def create_cleanup_job() -> bool:
    """Create the cleanup job (daily at 2 AM)."""
    # Note: We'll need a cleanup endpoint in the future
    cleanup_url = f"{config.scheduler.service_url}/api/v1/cleanup"

    cmd = [
        "gcloud",
        "scheduler",
        "jobs",
        "create",
        "http",
        config.scheduler.cleanup_job_name,
        f"--schedule={config.scheduler.cleanup_schedule}",
        f"--time-zone={config.scheduler.cleanup_timezone}",
        f"--uri={cleanup_url}",
        "--http-method=POST",
        f"--location={config.scheduler.scheduler_region}",
        "--description=Daily cleanup of expired content (TTL cleanup)",
    ]
    return run_gcloud_command(cmd)


def show_configuration_summary() -> None:
    """Display the scheduling configuration and estimates."""
    print("\n" + "=" * 60)
    print("CLOUD SCHEDULER CONFIGURATION SUMMARY")
    print("=" * 60)
    sched = config.scheduler
    ingestion_line = (
        f"Ingestion Schedule: {sched.ingestion_schedule} "
        f"({sched.ingestion_timezone})"
    )
    cleanup_line = (
        f"Cleanup Schedule: {sched.cleanup_schedule} "
        f"({sched.cleanup_timezone})"
    )
    print(ingestion_line)
    print(cleanup_line)
    print(f"Service URL: {sched.service_url}")
    print(f"Region: {sched.scheduler_region}")
    print()
    print("ESTIMATED USAGE:")
    print(f"- Daily articles: ~{sched.daily_articles_estimate:,}")
    monthly_usage = f"- Monthly API requests: ~{sched.monthly_api_usage_estimate:,}"
    print(monthly_usage)
    print(f"- API usage: {sched.api_usage_percentage:.1f}% of 10,000 limit")
    print()
    print("JOBS TO CREATE:")
    print(f"1. {sched.ingestion_job_name} - Every 8 hours")
    print(f"2. {sched.cleanup_job_name} - Daily at 2 AM")
    print("=" * 60)


def main() -> None:
    """Main setup function."""
    print("🚀 Setting up Cloud Scheduler for aiFeelNews")

    show_configuration_summary()

    # Confirm setup
    response = input("\nProceed with Cloud Scheduler setup? (y/N): ")
    if response.lower() != "y":
        print("Setup cancelled.")
        return

    db_url = config.database.database_url
    print(f"\n📋 Creating jobs in project: {db_url}")

    success_count = 0

    # Create ingestion job
    print("\n1. Creating ingestion job...")
    if create_ingestion_job():
        success_count += 1

    # Create cleanup job (optional - endpoint doesn't exist yet)
    print("\n2. Creating cleanup job...")
    print("⚠️  Note: Cleanup endpoint not implemented yet - skipping")
    # if create_cleanup_job():
    #     success_count += 1

    print("\n" + "=" * 60)
    if success_count > 0:
        print(f"✅ Successfully created {success_count} Cloud Scheduler job(s)")
        print("\nNext steps:")
        print("- Monitor jobs in Google Cloud Console")
        print("- Check ingestion logs in Cloud Run")
        print("- Implement /api/v1/cleanup endpoint for TTL cleanup")
    else:
        print("❌ Failed to create Cloud Scheduler jobs")
        print("Check your GCP authentication and permissions")
        sys.exit(1)


if __name__ == "__main__":
    main()
