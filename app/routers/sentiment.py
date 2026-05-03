"""
Sentiment analysis API endpoints.

Rate limit: ``config.security.rate_limit_sentiment`` (default 60/minute)
applied per-IP via slowapi.
"""

from typing import Dict, List, Union

from fastapi import APIRouter, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import config

# Import at module level to catch import errors early
from app.utils.sentiment import get_sentiment_provider_info

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
        # Return basic info if there's a function call issue
        return {
            "provider": "ERROR",
            "error": str(e),
            "fallback_enabled": True,
            "supported_languages": ["en"],
        }
