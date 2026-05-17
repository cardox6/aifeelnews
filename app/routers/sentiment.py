"""
Sentiment analysis API endpoints.

Rate limit: ``config.security.rate_limit_sentiment`` (default 60/minute)
applied per-IP via slowapi.
"""

import logging
from typing import Dict, List, Union

from fastapi import APIRouter, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import config

# Import at module level to catch import errors early
from app.utils.sentiment import get_sentiment_provider_info

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sentiment"])

_limiter = Limiter(key_func=get_remote_address)
_RATE = config.security.rate_limit_sentiment


@router.get("/info")
@_limiter.limit(_RATE)
def get_provider_info(
    request: Request,
) -> Dict[str, Union[str, float, bool, List[str], None]]:
    """
    Get information about the current sentiment analysis provider.

    Returns:
        Dictionary containing provider information including:
        - provider: Current provider (VADER or GCP_NL)
        - fallback_enabled: Whether fallback is enabled
        - supported_languages: List of supported languages
        - thresholds: Provider-specific thresholds
    """
    try:
        return get_sentiment_provider_info()
    except Exception as e:
        # Log the detail server-side; return a generic marker so internal
        # exception text is not exposed to the client
        # (CodeQL py/stack-trace-exposure).
        logger.error("Sentiment provider info lookup failed: %s", e, exc_info=True)
        return {
            "provider": "ERROR",
            "error": "provider info unavailable",
            "fallback_enabled": True,
            "supported_languages": ["en"],
        }
