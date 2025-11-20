"""
Robots.txt compliance checker for ethical web crawling.

This module ensures we respect website crawling policies by:
1. Fetching and parsing robots.txt files
2. Checking if our User-Agent is allowed to crawl specific URLs
3. Caching robots.txt to avoid repeated requests
4. Handling crawl delays and rate limiting
"""

import logging
import os
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

# Configure logging
logger = logging.getLogger(__name__)

# Global cache for robots.txt parsers (domain -> RobotFileParser)
# In production, use Redis or similar for distributed caching
_robots_cache: Dict[str, Tuple[RobotFileParser, datetime]] = {}

# Cache TTL for robots.txt (24 hours)
ROBOTS_CACHE_TTL = timedelta(hours=24)

# Our User-Agent string (honest identification)
USER_AGENT = (
    "aifeelnews-bot/1.0 "
    "(+https://github.com/cardox6/aifeelnews; matias.cardone@code.berlin)"
)


def get_domain_from_url(url: str) -> str:
    """
    Extract domain from URL for robots.txt lookup.

    Args:
        url: Full article URL

    Returns:
        str: Domain (e.g., 'example.com')
    """
    parsed = urlparse(url)
    return parsed.netloc.lower()


def get_robots_txt_url(domain: str) -> str:
    """
    Construct robots.txt URL for a given domain.

    Args:
        domain: Domain name (e.g., 'example.com')

    Returns:
        str: robots.txt URL (e.g., 'https://example.com/robots.txt')
    """
    # Always use HTTPS first, fallback to HTTP if needed
    return f"https://{domain}/robots.txt"


def fetch_robots_txt(domain: str) -> Optional[RobotFileParser]:
    """
    Fetch and parse robots.txt for a domain.

    Args:
        domain: Domain name

    Returns:
        RobotFileParser or None if fetch fails
    """
    robots_url = get_robots_txt_url(domain)

    try:
        logger.debug(f"Fetching robots.txt from {robots_url}")

        # Fetch with timeout and proper headers
        response = requests.get(
            robots_url,
            headers={"User-Agent": USER_AGENT},
            timeout=10,
            allow_redirects=True,
        )

        # Handle different response codes
        if response.status_code == 404:
            logger.info(f"No robots.txt found for {domain} (404) - allowing all")
            # No robots.txt means we can crawl (permissive default)
            rp = RobotFileParser()
            rp.set_url(robots_url)
            return rp

        response.raise_for_status()

        # Parse robots.txt content using the standard approach
        rp = RobotFileParser()
        rp.set_url(robots_url)

        # Store content and let parser fetch it
        # Write content to temp file and let parser read it
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as tmp_file:
            tmp_file.write(response.text)
            tmp_file_path = tmp_file.name

        try:
            # Create new parser that reads from our temp file
            temp_rp = RobotFileParser()
            temp_rp.set_url(f"file://{tmp_file_path}")
            temp_rp.read()

            # Copy the parsed rules to our main parser
            rp = temp_rp
        finally:
            # Clean up temp file
            os.unlink(tmp_file_path)

        logger.info(f"Successfully parsed robots.txt for {domain}")
        return rp

    except requests.RequestException as e:
        logger.warning(f"Failed to fetch robots.txt for {domain}: {e}")

        # Try HTTP fallback if HTTPS failed
        if robots_url.startswith("https://"):
            try:
                http_url = robots_url.replace("https://", "http://")
                logger.debug(f"Trying HTTP fallback: {http_url}")

                response = requests.get(
                    http_url,
                    headers={"User-Agent": USER_AGENT},
                    timeout=10,
                    allow_redirects=True,
                )

                if response.status_code == 200:
                    # Use same temp file approach for HTTP fallback
                    with tempfile.NamedTemporaryFile(
                        mode="w", suffix=".txt", delete=False
                    ) as tmp_file:
                        tmp_file.write(response.text)
                        tmp_file_path = tmp_file.name

                    try:
                        rp = RobotFileParser()
                        rp.set_url(f"file://{tmp_file_path}")
                        rp.read()
                        logger.info(
                            f"Successfully parsed robots.txt for {domain} via HTTP"
                        )
                        return rp
                    finally:
                        os.unlink(tmp_file_path)

            except requests.RequestException:
                pass

        # If all fails, be permissive (allow crawling)
        logger.warning(f"Cannot fetch robots.txt for {domain}, assuming permissive")
        return None

    except Exception as e:
        logger.error(f"Error parsing robots.txt for {domain}: {e}")
        return None


def get_robots_parser(domain: str) -> Optional[RobotFileParser]:
    """
    Get robots.txt parser for domain, using cache when possible.

    Args:
        domain: Domain name

    Returns:
        RobotFileParser or None
    """
    now = datetime.now(timezone.utc)

    # Check cache first
    if domain in _robots_cache:
        parser, cached_at = _robots_cache[domain]
        if now - cached_at < ROBOTS_CACHE_TTL:
            logger.debug(f"Using cached robots.txt for {domain}")
            return parser
        else:
            logger.debug(f"Robots.txt cache expired for {domain}")
            del _robots_cache[domain]

    # Fetch fresh robots.txt
    fresh_parser = fetch_robots_txt(domain)
    if fresh_parser:
        _robots_cache[domain] = (fresh_parser, now)
        return fresh_parser
    return None


def is_url_allowed(
    url: str, user_agent: str = USER_AGENT
) -> Tuple[bool, Optional[str]]:
    """
    Check if URL is allowed to be crawled according to robots.txt.

    Args:
        url: Full URL to check
        user_agent: User-Agent string to check against

    Returns:
        Tuple of (is_allowed: bool, reason: str or None)
    """
    try:
        domain = get_domain_from_url(url)

        # Get robots parser for domain
        parser = get_robots_parser(domain)

        if parser is None:
            # No robots.txt or failed to fetch - assume allowed
            return True, "No robots.txt or fetch failed (permissive default)"

        # Check if URL is allowed for our user agent
        allowed = parser.can_fetch(user_agent, url)

        if allowed:
            return True, "Allowed by robots.txt"
        else:
            return False, f"Disallowed by robots.txt for user-agent '{user_agent}'"

    except Exception as e:
        logger.error(f"Error checking robots.txt for {url}: {e}")
        # On error, be permissive
        return True, f"Error checking robots.txt: {e} (assuming allowed)"


def get_crawl_delay(domain: str, user_agent: str = USER_AGENT) -> Optional[float]:
    """
    Get crawl delay specified in robots.txt for domain and user-agent.

    Args:
        domain: Domain name
        user_agent: User-Agent string

    Returns:
        Crawl delay in seconds, or None if not specified
    """
    try:
        parser = get_robots_parser(domain)
        if parser is None:
            return None

        # Get crawl delay (this might not work with all robotparser versions)
        try:
            delay = parser.crawl_delay(user_agent)
            return float(delay) if delay else None
        except (AttributeError, ValueError):
            # Fallback: parse manually if crawl_delay method not available
            return None

    except Exception as e:
        logger.error(f"Error getting crawl delay for {domain}: {e}")
        return None


def respect_crawl_delay(
    domain: str, last_crawl_time: Optional[datetime] = None
) -> bool:
    """
    Check if enough time has passed since last crawl based on robots.txt delay.

    Args:
        domain: Domain name
        last_crawl_time: When we last crawled this domain

    Returns:
        True if we can crawl now, False if we should wait
    """
    if last_crawl_time is None:
        return True  # First crawl, go ahead

    # Get specified crawl delay
    delay = get_crawl_delay(domain)
    if delay is None:
        delay = 1.0  # Default 1 second delay for politeness

    # Check if enough time has passed
    now = datetime.now(timezone.utc)
    time_since_last = (now - last_crawl_time).total_seconds()

    if time_since_last >= delay:
        return True
    else:
        wait_time = delay - time_since_last
        logger.info(f"Need to wait {wait_time:.1f} seconds before crawling {domain}")
        return False


def check_robots_compliance(url: str) -> Dict[str, Any]:
    """
    Comprehensive robots.txt compliance check for a URL.

    Args:
        url: URL to check

    Returns:
        Dict with compliance information
    """
    domain = get_domain_from_url(url)
    allowed, reason = is_url_allowed(url)
    crawl_delay = get_crawl_delay(domain)

    return {
        "url": url,
        "domain": domain,
        "allowed": allowed,
        "reason": reason,
        "crawl_delay": crawl_delay,
        "user_agent": USER_AGENT,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    """Test robots.txt compliance with sample URLs."""

    # Configure logging for testing
    logging.basicConfig(level=logging.INFO)

    test_urls = [
        "https://www.bbc.com/news/technology",
        "https://techcrunch.com/2023/01/01/sample-article/",
        "https://www.reuters.com/business/",
        "https://example.com/test-article",
    ]

    print("🤖 Testing Robots.txt Compliance")
    print("=" * 50)

    for url in test_urls:
        print(f"\n📄 Testing: {url}")
        result = check_robots_compliance(url)

        print(f"   Domain: {result['domain']}")
        print(f"   Allowed: {'✅' if result['allowed'] else '❌'} {result['allowed']}")
        print(f"   Reason: {result['reason']}")
        if result["crawl_delay"]:
            print(f"   Crawl Delay: {result['crawl_delay']} seconds")
        print(f"   User-Agent: {result['user_agent']}")
