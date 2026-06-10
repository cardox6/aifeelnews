from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Union

if TYPE_CHECKING:
    from app.utils.gcp_nlp import AnnotateTextResult

from vaderSentiment.vaderSentiment import (  # type: ignore[import-untyped]
    SentimentIntensityAnalyzer,
)

from app.config import config

logger = logging.getLogger(__name__)

# VADER analyzer (always available as fallback)
vader_analyzer = SentimentIntensityAnalyzer()


def analyze_sentiment_vader(text: str) -> Tuple[str, float]:
    """Analyze sentiment using VADER sentiment analyzer (English lexicon only)."""
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


def _vader_fallback(text: str, language: str) -> Tuple[str, float]:
    """Fallback sentiment when GCP NL is unavailable.

    VADER is an English-only lexicon: on non-English text it finds no lexicon
    matches and collapses everything to ~0.0 / "neutral", which is silently
    misleading. So we only run VADER for English; for any other language we
    return an explicit neutral rather than a fake score.
    """
    if language != "en":
        logger.debug(
            "Skipping VADER fallback for language=%s (English-only lexicon); "
            "returning explicit neutral",
            language,
        )
        return "neutral", 0.0
    return analyze_sentiment_vader(text)


def analyze_sentiment_gcp_nl(
    text: str, language: str = "en"
) -> Tuple[str, float, Optional[float]]:
    """Analyze sentiment using Google Cloud Natural Language API.

    Supports German alongside English. On failure, falls back to VADER for
    English only (see :func:`_vader_fallback`).
    """
    try:
        from app.utils.gcp_nlp import gcp_nlp_client

        return gcp_nlp_client.analyze_sentiment(text, language)
    except ImportError as e:
        logger.warning(f"GCP NL client not available: {e}")
        label, score = _vader_fallback(text, language)
        return label, score, None
    except Exception as e:
        logger.warning(
            "GCP NL analyzeSentiment failed: %s; falling back",
            e,
            exc_info=True,
        )
        if config.sentiment.enable_fallback:
            label, score = _vader_fallback(text, language)
            return label, score, None
        else:
            return "neutral", 0.0, None


def annotate_text_gcp_nl(
    text: str, language: str = "en"
) -> Optional[AnnotateTextResult]:
    """
    Full annotateText using GCP NL (sentiment + entities + categories in one call).

    Returns None if GCP NL is unavailable or fails, so the caller
    can fall back to VADER for sentiment-only analysis.
    """
    try:
        from app.utils.gcp_nlp import gcp_nlp_client

        return gcp_nlp_client.annotate_text(text, language)
    except ImportError as e:
        logger.warning(f"GCP NL client not available: {e}")
        return None
    except Exception as e:
        logger.warning(
            "GCP NL annotateText failed: %s; falling back to VADER",
            e,
            exc_info=True,
        )
        return None


def analyze_sentiment(text: str, language: str = "en") -> Tuple[str, float]:
    """
    Analyze sentiment using the configured provider.

    Args:
        text: Text to analyze
        language: ISO 639-1 code of the text (e.g. "en", "de"). GCP NL supports
            German; the VADER fallback is English-only, so non-English text that
            falls through to VADER returns an explicit neutral instead.

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
        label, score, magnitude = analyze_sentiment_gcp_nl(text, language)
        return label, score
    elif provider == "VADER":
        logger.debug("Using VADER for sentiment analysis")
        return _vader_fallback(text, language)
    else:
        logger.warning(f"Unknown sentiment provider '{provider}', defaulting to VADER")
        return _vader_fallback(text, language)


def provisional_sentiment(text: str, language: str = "en") -> Tuple[str, float]:
    """Cheap ingestion-time sentiment — always free VADER, never GCP NL.

    A placeholder the crawl worker's authoritative ``annotateText`` overwrites,
    so it never spends a GCP NL unit regardless of ``SENTIMENT_PROVIDER``.
    Non-English returns neutral (VADER is English-only).
    """
    if not text:
        return "neutral", 0.0
    return _vader_fallback(text, language)


def get_sentiment_provider_info() -> Dict[
    str, Union[str, float, bool, List[str], None]
]:
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
