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
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.article import Article
from app.models.article_content import ArticleContent
from app.models.crawl_job import CrawlJob, CrawlStatus
from app.models.sentiment_analysis import SentimentAnalysis
from app.utils.logging import setup_logging
from app.utils.robots import (
    check_robots_compliance,
    get_domain_from_url,
    respect_crawl_delay,
)
from app.utils.sentiment import analyze_sentiment
from app.utils.ttl import calculate_content_expiry

# Use the central structured-logging setup so standalone worker runs
# emit the same Cloud-Logging-friendly JSON as the web app.
setup_logging()
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

        article_text: Optional[str] = None

        # Try each selector until we find content
        for selector in content_selectors:
            elements = soup.select(selector)
            if elements:
                # Take the first matching element
                element = elements[0]
                text_content: str = element.get_text(strip=True, separator=" ")
                article_text = text_content
                if len(article_text) > 100:  # Must have substantial content
                    break

        # Fallback: extract from body if no article content found
        if not article_text or len(article_text) < 100:
            body = soup.find("body")
            if body:
                text_content = body.get_text(strip=True, separator=" ")
                article_text = text_content

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
        logger.error("Error extracting text from %s: %s", url, e, exc_info=True)
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

            crawl_job.status = CrawlStatus.FORBIDDEN_BY_ROBOTS  # type: ignore
            crawl_job.error_message = robots_check["reason"]  # type: ignore
            crawl_job.updated_at = datetime.now(timezone.utc)  # type: ignore
            db.commit()
            return False

        logger.info(f"✅ Robots.txt allows crawling: {domain}")

        # Step 2: Respect crawl delays and rate limiting
        last_crawl = _last_crawl_times.get(domain)
        if not respect_crawl_delay(domain, last_crawl):
            logger.info(f"⏳ Rate limiting active for {domain}, will retry later")

            crawl_job.status = CrawlStatus.RATE_LIMITED  # type: ignore
            msg = "Rate limited - respecting crawl delay"
            crawl_job.error_message = msg  # type: ignore
            crawl_job.updated_at = datetime.now(timezone.utc)  # type: ignore
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
            crawl_job.status = CrawlStatus.FAILED  # type: ignore
            msg = "No article content could be extracted"
            crawl_job.error_message = msg  # type: ignore
            crawl_job.updated_at = datetime.now(timezone.utc)  # type: ignore
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
            existing_content.content_text = truncated_text  # type: ignore
            existing_content.content_hash = content_hash  # type: ignore
            existing_content.content_length = len(article_text)  # type: ignore
            existing_content.extracted_at = datetime.now(timezone.utc)  # type: ignore
            existing_content.expires_at = calculate_content_expiry()  # type: ignore
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

        # Step 6: NLP analysis (sentiment + entities + categories)
        logger.debug(f"Analyzing article content for {url}")

        from app.config import config
        from app.models.article_category import ArticleCategory
        from app.models.article_entity import ArticleEntity
        from app.models.entity import Entity
        from app.utils.sentiment import annotate_text_gcp_nl

        provider = config.sentiment.sentiment_provider
        magnitude = None
        model_name = "vader_lexicon"
        entities_stored = 0
        categories_stored = 0

        # The article's language (from Mediastack) drives the GCP NL model so
        # German content is analyzed in German (sentiment + entities + V2-model
        # categories), not forced through the English path.
        article_language = article.language or "en"

        if provider == "GCP_NL":
            # Single annotateText call: sentiment + entities + categories
            result = annotate_text_gcp_nl(article_text, language=article_language)

            if result is not None:
                sentiment_label = result.sentiment_label
                sentiment_score = result.sentiment_score
                magnitude = result.sentiment_magnitude
                model_name = "gcp_nl_v1"

                # Store entities — data arrives deduplicated from gcp_nlp.py
                for ent in result.entities:
                    # Truncate fields to fit DB column limits — GCP NL
                    # can return arbitrarily long names
                    entity_name = ent.name[:255]
                    entity_wiki_url = (
                        ent.wikipedia_url[:1000] if ent.wikipedia_url else None
                    )
                    entity_mid = ent.mid[:100] if ent.mid else None

                    canonical = (
                        db.query(Entity)
                        .filter(Entity.name == entity_name, Entity.type == ent.type)
                        .first()
                    )
                    if not canonical:
                        try:
                            canonical = Entity(
                                name=entity_name,
                                type=ent.type,
                                wikipedia_url=entity_wiki_url,
                                mid=entity_mid,
                            )
                            db.add(canonical)
                            db.flush()
                        except (IntegrityError, DataError) as exc:
                            db.rollback()
                            if isinstance(exc, DataError):
                                logger.warning(
                                    "Skipping entity with invalid data: "
                                    f"{entity_name[:80]}/{ent.type}"
                                )
                                continue
                            # IntegrityError: concurrent worker created it — read back
                            canonical = (
                                db.query(Entity)
                                .filter(
                                    Entity.name == entity_name,
                                    Entity.type == ent.type,
                                )
                                .first()
                            )
                            if not canonical:
                                logger.error(
                                    "Entity %s/%s missing after IntegrityError",
                                    entity_name[:80],
                                    ent.type,
                                    exc_info=True,
                                )
                                continue

                    # Re-analysis guard: update if link already exists
                    existing_link = (
                        db.query(ArticleEntity)
                        .filter(
                            ArticleEntity.article_id == article.id,
                            ArticleEntity.entity_id == canonical.id,
                        )
                        .first()
                    )
                    if existing_link:
                        existing_link.salience = ent.salience  # type: ignore[assignment]
                        existing_link.mention_count = ent.mention_count  # type: ignore[assignment]
                    else:
                        article_entity = ArticleEntity(
                            article_id=article.id,
                            entity_id=canonical.id,
                            salience=ent.salience,
                            mention_count=ent.mention_count,
                        )
                        db.add(article_entity)
                    entities_stored += 1

                # Store categories
                for cat in result.categories:
                    article_category = ArticleCategory(
                        article_id=article.id,
                        name=cat.name,
                        confidence=cat.confidence,
                    )
                    db.add(article_category)
                    categories_stored += 1
            else:
                # GCP NL failed — fall back to VADER for sentiment only
                # (English text only; non-English returns explicit neutral).
                logger.warning("GCP NL annotateText failed, falling back to VADER")
                sentiment_label, sentiment_score = analyze_sentiment(
                    article_text, language=article_language
                )
        else:
            # VADER provider — sentiment only, no entities/categories
            sentiment_label, sentiment_score = analyze_sentiment(
                article_text, language=article_language
            )

        # Store sentiment analysis record
        sentiment_analysis = SentimentAnalysis(
            article_id=article.id,
            provider=provider if model_name == "gcp_nl_v1" else "VADER",
            model_name=model_name,
            score=sentiment_score,
            magnitude=magnitude,
            label=sentiment_label,
            language=article_language,
        )
        db.add(sentiment_analysis)

        # Update denormalized article fields
        article.sentiment_label = sentiment_label  # type: ignore[assignment]
        article.sentiment_score = sentiment_score  # type: ignore[assignment]
        # magnitude is None for VADER (incl. the GCP-NL→VADER fallback above),
        # set only when GCP NL annotateText succeeded.
        article.sentiment_magnitude = magnitude  # type: ignore[assignment]

        # Step 7: Mark crawl job as successful
        crawl_job.status = CrawlStatus.SUCCESS  # type: ignore[assignment]
        crawl_job.error_message = None  # type: ignore[assignment]
        crawl_job.updated_at = datetime.now(timezone.utc)  # type: ignore[assignment]

        db.commit()

        # Step 8: Queue events for BigQuery analytics (if enabled)
        try:
            from app.services.bigquery import (
                queue_category_event,
                queue_entity_event,
                queue_sentiment_event,
            )

            queue_sentiment_event(
                article_id=article.id,
                article_url=article.url,
                article_title=article.title or "",
                source_name=article.source.name,
                published_at=article.published_at,
                sentiment_score=sentiment_score,
                sentiment_label=sentiment_label,
                sentiment_provider=provider,
                model_name=model_name,
                magnitude=magnitude,
                language=article.language,
                content_length=len(article_text),
            )

            # Stream entity events (GCP_NL only)
            if provider == "GCP_NL" and result is not None:
                for ent in result.entities:
                    queue_entity_event(
                        article_id=article.id,
                        article_url=article.url,
                        article_title=article.title or "",
                        source_name=article.source.name,
                        published_at=article.published_at,
                        entity_name=ent.name,
                        entity_type=ent.type,
                        salience=ent.salience,
                        mention_count=ent.mention_count,
                        sentiment_label=sentiment_label,
                        sentiment_score=sentiment_score,
                        wikipedia_url=ent.wikipedia_url,
                        language=article_language,
                    )

                # Stream category events (GCP_NL only)
                for cat in result.categories:
                    queue_category_event(
                        article_id=article.id,
                        source_name=article.source.name,
                        published_at=article.published_at,
                        category_name=cat.name,
                        category_confidence=cat.confidence,
                        sentiment_label=sentiment_label,
                        sentiment_score=sentiment_score,
                        language=article_language,
                    )
        except Exception as e:
            logger.warning("BigQuery streaming failed: %s", e, exc_info=True)

        logger.info(f"✅ Successfully crawled and processed: {url}")
        magnitude_info = f", magnitude={magnitude:.3f}" if magnitude else ""
        sentiment_info = (
            f"   Sentiment ({provider}): {sentiment_label} "
            f"({sentiment_score:.3f}{magnitude_info})"
        )
        logger.info(sentiment_info)
        logger.info(f"   Entities: {entities_stored}, Categories: {categories_stored}")
        content_info = (
            f"   Content: {len(article_text)} chars → "
            f"{len(truncated_text)} chars stored"
        )
        logger.info(content_info)

        return True

    except requests.RequestException as e:
        logger.error("Network error crawling %s: %s", url, e, exc_info=True)
        # Order matters: rollback FIRST clears any aborted-session state from
        # an earlier failed commit (e.g. an IntegrityError on the success
        # path), THEN we set fields on crawl_job, THEN we commit. Setting
        # fields before rollback would discard them.
        db.rollback()
        crawl_job.status = CrawlStatus.FAILED  # type: ignore[assignment]
        crawl_job.error_code = "NETWORK_ERROR"  # type: ignore[assignment]
        crawl_job.error_message = f"Network error: {str(e)}"  # type: ignore[assignment]
        crawl_job.updated_at = datetime.now(timezone.utc)  # type: ignore[assignment]
        try:
            db.commit()
        except Exception as commit_err:
            logger.error(
                "Failed to record crawl failure: %s", commit_err, exc_info=True
            )
            db.rollback()
        return False

    except Exception as e:
        logger.error("Unexpected error crawling %s: %s", url, e, exc_info=True)
        # See above — rollback before re-mutating crawl_job. Without this,
        # a failed earlier commit leaves the session in PendingRollbackError
        # and the second commit propagates, the job stays in its prior
        # status (often IN_PROGRESS), and the worker retries it forever.
        db.rollback()
        crawl_job.status = CrawlStatus.FAILED  # type: ignore
        crawl_job.error_code = "PROCESSING_ERROR"  # type: ignore
        crawl_job.error_message = f"Processing error: {str(e)}"  # type: ignore
        crawl_job.updated_at = datetime.now(timezone.utc)  # type: ignore
        try:
            db.commit()
        except Exception as commit_err:
            logger.error(
                "Failed to record crawl failure: %s", commit_err, exc_info=True
            )
            db.rollback()
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
    # Newest jobs first: paired with newest-first job creation, this keeps the
    # latest articles flowing through GCP NL rather than being starved behind a
    # large historical backlog.
    jobs = (
        db.query(CrawlJob)
        .filter(CrawlJob.status == CrawlStatus.PENDING)  # type: ignore[arg-type]
        .order_by(CrawlJob.created_at.desc())
        .limit(limit)
        .all()
    )
    return list(jobs)


def create_crawl_jobs_for_articles(db: Session, limit: int = 100) -> int:
    """
    Create crawl jobs for articles that don't have them yet.

    Newest articles first (``published_at DESC``): the daily ingestion should
    push the latest articles through the crawl → GCP NL path promptly. Without
    the ordering the query returned an arbitrary (effectively oldest) slice, so
    freshly-ingested articles fell to the back of an ever-growing backlog and
    never got entity/category analysis.

    Args:
        db: Database session
        limit: Maximum number of jobs to create

    Returns:
        Number of crawl jobs created
    """
    # Find articles without crawl jobs, newest first.
    articles_without_jobs = (
        db.query(Article)
        .filter(~Article.id.in_(db.query(CrawlJob.article_id).distinct()))  # type: ignore
        .order_by(Article.published_at.desc())
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
        from app.config import config

        start_time = time.time()

        # Create crawl jobs for articles that don't have them. Enqueue up to the
        # configured creation limit (newest first) so creation keeps pace with
        # processing instead of leaving the latest articles un-crawled.
        new_jobs = create_crawl_jobs_for_articles(
            db, limit=config.scheduler.max_crawl_job_creation
        )

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
                logger.error(
                    "Error processing crawl job %s: %s", job.id, e, exc_info=True
                )
                failed_crawls += 1

        total_time = time.time() - start_time

        # Flush any remaining BigQuery events from the batch buffer
        try:
            from app.services.bigquery import flush_sentiment

            flush_sentiment()
        except Exception as e:
            logger.debug(f"BigQuery flush failed (optional): {e}")

        logger.info("🏁 Crawl worker completed:")
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

    print("\n📊 Crawl Worker Results:")
    print(f"   Status: {result['status']}")
    print(f"   Jobs Processed: {result['processed']}")
    print(f"   Successful Crawls: {result['successful']}")
    print(f"   Failed Crawls: {result['failed']}")
    print(f"   New Jobs Created: {result['new_jobs_created']}")
    print(f"   Duration: {result['duration']:.2f} seconds")
