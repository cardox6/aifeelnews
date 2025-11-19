#!/usr/bin/env python3
"""
Command line interface for running crawl jobs.

This script provides an easy way to run the crawl worker
with various configurations and settings.
"""

import argparse
import sys
from datetime import datetime

from app.jobs.crawl_worker import run_crawl_worker


def main():
    """Main CLI entry point."""
    
    parser = argparse.ArgumentParser(
        description="Run the aiFeelNews crawl worker to process article content"
    )
    
    parser.add_argument(
        "--max-jobs", 
        type=int, 
        default=10,
        help="Maximum number of crawl jobs to process (default: 10)"
    )
    
    parser.add_argument(
        "--verbose", 
        action="store_true",
        help="Enable verbose logging output"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true", 
        help="Show what would be done without actually crawling"
    )
    
    args = parser.parse_args()
    
    print(f"🚀 aiFeelNews Crawl Worker")
    print(f"{'=' * 50}")
    print(f"Max jobs: {args.max_jobs}")
    print(f"Verbose: {args.verbose}")
    print(f"Dry run: {args.dry_run}")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No actual crawling will be performed")
        print("This would normally:")
        print("  1. Create crawl jobs for articles without them")
        print("  2. Process pending crawl jobs")
        print("  3. Check robots.txt compliance")
        print("  4. Extract article content") 
        print("  5. Perform sentiment analysis")
        print("  6. Store truncated content with TTL")
        return
    
    # Run the crawl worker
    try:
        result = run_crawl_worker(max_jobs=args.max_jobs)
        
        print("📊 Crawl Results:")
        print("=" * 30)
        print(f"Status: {result['status']}")
        print(f"Jobs Processed: {result['processed']}")
        print(f"Successful: {result['successful']}")
        print(f"Failed: {result['failed']}")
        print(f"New Jobs Created: {result['new_jobs_created']}")
        print(f"Duration: {result['duration']:.2f} seconds")
        
        if result['processed'] == 0:
            print("\nℹ️ No jobs were processed.")
            print("This could mean:")
            print("  - No articles exist in the database")
            print("  - All articles already have crawl jobs")
            print("  - All jobs are already completed")
            print("\nTry running the ingestion pipeline first:")
            print("  python -m app.jobs.run_ingestion")
        
        elif result['failed'] > 0:
            print(f"\n⚠️ {result['failed']} jobs failed.")
            print("Common failure reasons:")
            print("  - Robots.txt blocked crawling")
            print("  - Rate limiting (jobs will retry later)")
            print("  - Network timeouts or errors")
            print("  - Content extraction failures")
        
        if result['successful'] > 0:
            print(f"\n✅ Successfully crawled {result['successful']} articles!")
            print("Content stored with:")
            print("  - 1024 character truncation (data minimisation)")
            print("  - 7-day TTL for automatic cleanup")
            print("  - Sentiment analysis (VADER)")
            print("  - Full robots.txt compliance")
            
    except KeyboardInterrupt:
        print("\n\n⏹️ Crawl worker interrupted by user")
        sys.exit(1)
        
    except Exception as e:
        print(f"\n❌ Error running crawl worker: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()