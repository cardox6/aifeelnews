"""
Web crawl worker for ethical article content extraction.

This worker:
1. Processes PENDING crawl jobs from the database
2. Checks robots.txt compliance before crawling
3. Extracts article content with proper rate limiting
4. Stores content with TTL and performs sentiment analysis
5. Updates crawl job status with detailed results
"""

import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.article import Article
from app.models.article_content import ArticleContent
from app.models.crawl_job import CrawlJob, CrawlStatus
from app.models.sentiment_analysis import SentimentAnalysis
from app.utils.robots import (
    check_robots_compliance,
    get_domain_from_url,
    respect_crawl_delay,
)
from app.utils.sentiment import analyze_sentiment
from app.utils.ttl import calculate_content_expiry

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Track last crawl time per domain for rate limiting
_last_crawl_times: Dict[str, datetime] = {}


def extract_article_text(html_content: str, url: str) -> Optional[str]:
    """
    Extract main article text from HTML content.

    Args:
        html_content: Raw HTML content
        url: Article URL (for context/debugging)

    Returns:
        Extracted text or None if extraction fails
    """
    try:
        soup = BeautifulSoup(html_content, "html.parser")

        # Remove script, style, and other non-content elements
        for script in soup(["script", "style", "nav", "header", "footer", "aside"]):
            script.decompose()

        # Try common article content selectors (in order of preference)
        content_selectors = [
            "article",
            '[role="article"]',
            ".article-content",
            ".article-body",
            ".entry-content",
            ".post-content",
            ".content",
            "main",
            ".main-content",
        ]

        article_text = None

        # Try each selector until we find content
        for selector in content_selectors:
            elements = soup.select(selector)
            if elements:
                # Take the first matching element
                element = elements[0]
                article_text = element.get_text(strip=True, separator=" ")
                if len(article_text) > 100:  # Must have substantial content
                    break

        # Fallback: extract from body if no article content found
        if not article_text or len(article_text) < 100:
            body = soup.find("body")
            if body:
                article_text = body.get_text(strip=True, separator=" ")

        # Clean up the text
        if article_text:
            # Remove excessive whitespace
            lines = article_text.split("\n")
            cleaned_lines = [line.strip() for line in lines if line.strip()]
            article_text = "\n".join(cleaned_lines)

            # Limit length (for data minimisation)
            if len(article_text) > 5000:  # We'll truncate to 1024 for storage
                logger.info(
                    f"Article text is {len(article_text)} chars, will be truncated"
                )

            return article_text

        return None

    except Exception as e:
        logger.error(f"Error extracting text from {url}: {e}")
        return None


def crawl_article(crawl_job: CrawlJob, db: Session) -> bool:
    """
    Crawl a single article and update the crawl job.

    Args:
        crawl_job: CrawlJob instance to process
        db: Database session

    Returns:
        True if crawl was successful, False otherwise
    """
    # Initialize variables at the top to avoid scope issues
    article = crawl_job.article
    url = article.url
    domain = get_domain_from_url(url)

    try:

        logger.info(f"🔍 Crawling: {url}")

        # Update status to in progress
        crawl_job.status = CrawlStatus.IN_PROGRESS  # type: ignore[assignment]
        crawl_job.updated_at = datetime.now(timezone.utc)  # type: ignore[assignment]
        db.commit()

        # Step 1: Check robots.txt compliance
        logger.debug(f"Checking robots.txt for {domain}")
        robots_check = check_robots_compliance(url)
        crawl_job.robots_allowed = robots_check["allowed"]  # type: ignore[assignment]

        if not robots_check["allowed"]:
            logger.warning(f"❌ Crawling blocked by robots.txt: {url}")
            logger.warning(f"   Reason: {robots_check['reason']}")

            crawl_job.status = CrawlStatus.FORBIDDEN_BY_ROBOTS  # type: ignore[assignment]
            crawl_job.error_message = robots_check["reason"]  # type: ignore[assignment]
            crawl_job.updated_at = datetime.now(timezone.utc)  # type: ignore[assignment]
            db.commit()
            return False

        logger.info(f"✅ Robots.txt allows crawling: {domain}")

        # Step 2: Respect crawl delays and rate limiting
        last_crawl = _last_crawl_times.get(domain)
        if not respect_crawl_delay(domain, last_crawl):
            logger.info(f"⏳ Rate limiting active for {domain}, will retry later")

            crawl_job.status = CrawlStatus.RATE_LIMITED  # type: ignore[assignment]
            crawl_job.error_message = "Rate limited - respecting crawl delay"  # type: ignore[assignment]
            crawl_job.updated_at = datetime.now(timezone.utc)  # type: ignore[assignment]
            db.commit()
            return False

        # Step 3: Fetch the article content
        logger.debug(f"Fetching content from {url}")

        headers = {
            "User-Agent": settings.CRAWLER_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

        start_time = time.time()

        response = requests.get(
            url,
            headers=headers,
            timeout=settings.CRAWLER_REQUEST_TIMEOUT,
            allow_redirects=True,
        )

        # Update crawl timing
        _last_crawl_times[domain] = datetime.now(timezone.utc)
        fetch_time = time.time() - start_time

        # Check response
        response.raise_for_status()

        crawl_job.http_status = response.status_code  # type: ignore[assignment]
        crawl_job.bytes_downloaded = len(response.content)  # type: ignore[assignment]
        crawl_job.fetched_at = datetime.now(timezone.utc)  # type: ignore[assignment]

        logger.info(f"📦 Fetched {len(response.content)} bytes in {fetch_time:.2f}s")

        # Step 4: Extract article text
        article_text = extract_article_text(response.text, url)

        if not article_text:
            logger.warning(f"⚠️ No article content extracted from {url}")
            crawl_job.status = CrawlStatus.FAILED  # type: ignore[assignment]
            crawl_job.error_message = "No article content could be extracted"  # type: ignore[assignment]
            crawl_job.updated_at = datetime.now(timezone.utc)  # type: ignore[assignment]
            db.commit()
            return False

        logger.info(f"📄 Extracted {len(article_text)} characters of text")

        # Step 5: Store article content (truncated with TTL)
        truncated_text = article_text[:1024]  # Data minimisation: max 1024 chars
        content_hash = hashlib.sha256(article_text.encode()).hexdigest()

        # Check if content already exists
        existing_content = (
            db.query(ArticleContent).filter_by(article_id=article.id).first()
        )

        if existing_content:
            logger.info(f"📝 Updating existing content for article {article.id}")
            existing_content.content_text = truncated_text  # type: ignore[assignment]
            existing_content.content_hash = content_hash  # type: ignore[assignment]
            existing_content.content_length = len(article_text)  # type: ignore[assignment]
            existing_content.extracted_at = datetime.now(timezone.utc)  # type: ignore[assignment]
            existing_content.expires_at = calculate_content_expiry()  # type: ignore[assignment]
        else:
            logger.info(f"📝 Creating new content for article {article.id}")
            content = ArticleContent(
                article_id=article.id,
                content_text=truncated_text,
                content_hash=content_hash,
                content_length=len(article_text),
                expires_at=calculate_content_expiry(),
            )
            db.add(content)

        # Step 6: Perform sentiment analysis
        logger.debug(f"Analyzing sentiment for {url}")
        sentiment_label, sentiment_score = analyze_sentiment(article_text)

        # Store sentiment analysis
        sentiment_analysis = SentimentAnalysis(
            article_id=article.id,
            provider="VADER",
            model_name="vader_lexicon",
            score=sentiment_score,
            label=sentiment_label,
            language=article.language or "en",
        )
        db.add(sentiment_analysis)

        # Update article with sentiment (for quick access)
        article.sentiment_label = sentiment_label  # type: ignore[assignment]
        article.sentiment_score = sentiment_score  # type: ignore[assignment]

        # Step 7: Mark crawl job as successful
        crawl_job.status = CrawlStatus.SUCCESS  # type: ignore[assignment]
        crawl_job.error_message = None  # type: ignore[assignment]
        crawl_job.updated_at = datetime.now(timezone.utc)  # type: ignore[assignment]

        db.commit()

        logger.info(f"✅ Successfully crawled and processed: {url}")
        logger.info(f"   Sentiment: {sentiment_label} ({sentiment_score:.3f})")
        logger.info(
            f"   Content: {len(article_text)} chars → {len(truncated_text)} chars stored"
        )

        return True

    except requests.RequestException as e:
        logger.error(f"❌ Network error crawling {url}: {e}")

        crawl_job.status = CrawlStatus.FAILED  # type: ignore[assignment]
        crawl_job.error_code = "NETWORK_ERROR"  # type: ignore[assignment]
        crawl_job.error_message = f"Network error: {str(e)}"  # type: ignore[assignment]
        crawl_job.updated_at = datetime.now(timezone.utc)  # type: ignore[assignment]
        db.commit()

        return False

    except Exception as e:
        logger.error(f"❌ Unexpected error crawling {url}: {e}")

        crawl_job.status = CrawlStatus.FAILED  # type: ignore[assignment]
        crawl_job.error_code = "PROCESSING_ERROR"  # type: ignore[assignment]
        crawl_job.error_message = f"Processing error: {str(e)}"  # type: ignore[assignment]
        crawl_job.updated_at = datetime.now(timezone.utc)  # type: ignore[assignment]
        db.commit()

        return False


def get_pending_crawl_jobs(db: Session, limit: int = 10) -> List[CrawlJob]:
    """
    Get pending crawl jobs from the database.

    Args:
        db: Database session
        limit: Maximum number of jobs to fetch

    Returns:
        List of pending CrawlJob instances
    """
    return (
        db.query(CrawlJob)
        .filter(CrawlJob.status == CrawlStatus.PENDING)  # type: ignore[arg-type]
        .order_by(CrawlJob.created_at)
        .limit(limit)
        .all()
    )


def create_crawl_jobs_for_articles(db: Session, limit: int = 20) -> int:
    """
    Create crawl jobs for articles that don't have them yet.

    Args:
        db: Database session
        limit: Maximum number of jobs to create

    Returns:
        Number of crawl jobs created
    """
    # Find articles without crawl jobs
    articles_without_jobs = (
        db.query(Article)
        .filter(~Article.id.in_(db.query(CrawlJob.article_id).distinct()))  # type: ignore[arg-type]
        .limit(limit)
        .all()
    )

    created_count = 0

    for article in articles_without_jobs:
        crawl_job = CrawlJob(article_id=article.id, status=CrawlStatus.PENDING)
        db.add(crawl_job)
        created_count += 1

        logger.debug(f"Created crawl job for article: {article.url}")

    if created_count > 0:
        db.commit()
        logger.info(f"📝 Created {created_count} new crawl jobs")

    return created_count


def run_crawl_worker(max_jobs: int = 5) -> Dict[str, Any]:
    """
    Run the crawl worker to process pending jobs.

    Args:
        max_jobs: Maximum number of jobs to process in this run

    Returns:
        Summary statistics of the crawl run
    """
    logger.info(f"🚀 Starting crawl worker (max {max_jobs} jobs)")

    db = SessionLocal()

    try:
        start_time = time.time()

        # Create crawl jobs for articles that don't have them
        new_jobs = create_crawl_jobs_for_articles(db)

        # Get pending crawl jobs
        pending_jobs = get_pending_crawl_jobs(db, max_jobs)

        if not pending_jobs:
            logger.info("ℹ️ No pending crawl jobs found")
            return {
                "status": "completed",
                "processed": 0,
                "successful": 0,
                "failed": 0,
                "new_jobs_created": new_jobs,
                "duration": time.time() - start_time,
            }

        logger.info(f"📋 Found {len(pending_jobs)} pending crawl jobs")

        successful_crawls = 0
        failed_crawls = 0

        for job in pending_jobs:
            try:
                if crawl_article(job, db):
                    successful_crawls += 1
                else:
                    failed_crawls += 1

                # Brief pause between crawls for politeness
                time.sleep(0.5)

            except Exception as e:
                logger.error(f"❌ Error processing crawl job {job.id}: {e}")
                failed_crawls += 1

        total_time = time.time() - start_time

        logger.info(f"🏁 Crawl worker completed:")
        logger.info(f"   Processed: {len(pending_jobs)} jobs")
        logger.info(f"   Successful: {successful_crawls}")
        logger.info(f"   Failed: {failed_crawls}")
        logger.info(f"   New jobs created: {new_jobs}")
        logger.info(f"   Duration: {total_time:.2f} seconds")

        return {
            "status": "completed",
            "processed": len(pending_jobs),
            "successful": successful_crawls,
            "failed": failed_crawls,
            "new_jobs_created": new_jobs,
            "duration": total_time,
        }

    finally:
        db.close()


if __name__ == "__main__":
    """Run crawl worker as standalone script."""

    import sys

    # Get max jobs from command line or use default
    max_jobs = int(sys.argv[1]) if len(sys.argv) > 1 else 5

    result = run_crawl_worker(max_jobs)

    print(f"\n📊 Crawl Worker Results:")
    print(f"   Status: {result['status']}")
    print(f"   Jobs Processed: {result['processed']}")
    print(f"   Successful Crawls: {result['successful']}")
    print(f"   Failed Crawls: {result['failed']}")
    print(f"   New Jobs Created: {result['new_jobs_created']}")
    print(f"   Duration: {result['duration']:.2f} seconds")
