"""
Sentiment analysis API endpoints.
"""

from typing import Dict, List, Union

from fastapi import APIRouter

from app.utils.sentiment import get_sentiment_provider_info

router = APIRouter(prefix="/api/v1/sentiment", tags=["sentiment"])


@router.get("/info")
def get_provider_info() -> Dict[str, Union[str, float, bool, List[str], None]]:
    """
    Get information about the current sentiment analysis provider.

    Returns:
        Dictionary containing provider information including:
        - provider: Current provider (VADER or GCP_NL)
        - fallback_enabled: Whether fallback is enabled
        - supported_languages: List of supported languages
        - thresholds: Provider-specific thresholds
    """
    return get_sentiment_provider_info()