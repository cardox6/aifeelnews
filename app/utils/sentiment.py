import logging
from typing import Dict, List, Optional, Tuple, Union

from vaderSentiment.vaderSentiment import (  # type: ignore[import-untyped]
    SentimentIntensityAnalyzer,
)

from app.config import config

logger = logging.getLogger(__name__)

# VADER analyzer (always available as fallback)
vader_analyzer = SentimentIntensityAnalyzer()


def analyze_sentiment_vader(text: str) -> Tuple[str, float]:
    """Analyze sentiment using VADER sentiment analyzer."""
    if not text:
        return "neutral", 0.0

    score = vader_analyzer.polarity_scores(text)["compound"]

    positive_threshold = config.sentiment.vader_positive_threshold
    negative_threshold = config.sentiment.vader_negative_threshold

    if score >= positive_threshold:
        return "positive", score
    elif score <= negative_threshold:
        return "negative", score
    else:
        return "neutral", score


def analyze_sentiment_gcp_nl(text: str) -> Tuple[str, float, Optional[float]]:
    """Analyze sentiment using Google Cloud Natural Language API (English only)."""
    try:
        from app.utils.gcp_nlp import gcp_nlp_client

        return gcp_nlp_client.analyze_sentiment(text)
    except ImportError as e:
        logger.warning(f"GCP NL client not available: {e}")
        # Fall back to VADER
        label, score = analyze_sentiment_vader(text)
        return label, score, None
    except Exception as e:
        logger.error(f"Error in GCP NL sentiment analysis: {e}")
        # Fall back to VADER
        if config.sentiment.enable_fallback:
            logger.info("Falling back to VADER sentiment analysis")
            label, score = analyze_sentiment_vader(text)
            return label, score, None
        else:
            return "neutral", 0.0, None


def analyze_sentiment(text: str) -> Tuple[str, float]:
    """
    Analyze sentiment using the configured provider (English only).

    Optimized for English news articles matching our ingestion pipeline.

    Args:
        text: English text to analyze

    Returns:
        Tuple of (sentiment_label, sentiment_score)

    Note:
        This function abstracts away the provider details and returns
        a consistent interface regardless of whether VADER or GCP NL is used.
    """
    if not text:
        return "neutral", 0.0

    provider = config.sentiment.sentiment_provider.upper()

    if provider == "GCP_NL":
        logger.debug("Using Google Cloud Natural Language for sentiment analysis")
        label, score, magnitude = analyze_sentiment_gcp_nl(text)
        return label, score
    elif provider == "VADER":
        logger.debug("Using VADER for sentiment analysis")
        return analyze_sentiment_vader(text)
    else:
        logger.warning(f"Unknown sentiment provider '{provider}', defaulting to VADER")
        return analyze_sentiment_vader(text)


def get_sentiment_provider_info() -> (
    Dict[str, Union[str, float, bool, List[str], None]]
):
    """Get information about the current sentiment analysis provider."""
    provider = config.sentiment.sentiment_provider

    info: Dict[str, Union[str, float, bool, List[str], None]] = {
        "provider": provider,
        "fallback_enabled": config.sentiment.enable_fallback,
        "supported_languages": config.sentiment.supported_languages,
    }

    if provider == "VADER":
        info.update(
            {
                "positive_threshold": config.sentiment.vader_positive_threshold,
                "negative_threshold": config.sentiment.vader_negative_threshold,
            }
        )
    elif provider == "GCP_NL":
        info.update(
            {
                "positive_threshold": config.sentiment.gcp_nl_positive_threshold,
                "negative_threshold": config.sentiment.gcp_nl_negative_threshold,
                "project_id": config.sentiment.gcp_nl_project_id,
            }
        )

    return info
