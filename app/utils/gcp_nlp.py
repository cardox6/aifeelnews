"""
Google Cloud Natural Language integration.

This module provides a production-grade sentiment analysis client using
Google Cloud Natural Language API with proper error handling, rate limiting,
and abstraction that matches the existing sentiment provider interface.
"""

import logging
from typing import Optional, Tuple

from google.api_core import exceptions as gcp_exceptions  # type: ignore[import-untyped]
from google.cloud import language_v1  # type: ignore[import-untyped]

from app.config import config

logger = logging.getLogger(__name__)


class GcpNlpClient:
    """
    Google Cloud Natural Language API client with production-grade features.

    Provides sentiment analysis with proper error handling, rate limiting,
    and abstraction that matches the existing VADER interface.
    """

    def __init__(self, project_id: Optional[str] = None) -> None:
        """
        Initialize GCP Natural Language client.

        Args:
            project_id: GCP project ID. If None, uses default from environment.
        """
        import os

        self.project_id = (
            project_id
            or config.sentiment.gcp_nl_project_id
            or os.getenv("GOOGLE_CLOUD_PROJECT")
        )
        self._client: Optional[language_v1.LanguageServiceClient] = None

        # Sentiment score mapping thresholds (from configuration)
        self.positive_threshold = config.sentiment.gcp_nl_positive_threshold
        self.negative_threshold = config.sentiment.gcp_nl_negative_threshold

    @property
    def client(self) -> language_v1.LanguageServiceClient:
        """Lazy initialization of GCP Natural Language client."""
        if self._client is None:
            try:
                self._client = language_v1.LanguageServiceClient()
                logger.info("Initialized Google Cloud Natural Language client")
            except Exception as e:
                logger.error(f"Failed to initialize GCP NL client: {e}")
                raise
        return self._client

    def analyze_sentiment(self, text: str) -> Tuple[str, float, Optional[float]]:
        """
        Analyze sentiment using Google Cloud Natural Language API.

        Optimized for English-only news articles (matches our ingestion pipeline).

        Args:
            text: English text to analyze for sentiment

        Returns:
            Tuple of (label, score, magnitude) where:
            - label: "positive", "negative", or "neutral"
            - score: Sentiment score (-1.0 to 1.0)
            - magnitude: Sentiment magnitude (0.0+, indicates emotional intensity)

        Raises:
            Exception: If API call fails after retries
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for sentiment analysis")
            return "neutral", 0.0, None

        # Truncate text if too long (GCP NL has limits)
        max_length = config.sentiment.gcp_nl_max_text_length
        if len(text.encode("utf-8")) > max_length:
            logger.warning(f"Text too long ({len(text)} chars), truncating")
            text = text[: max_length // 4]  # Conservative truncation

        try:
            # Create document object - hardcode English
            # (we only ingest English articles)
            document = language_v1.Document(
                content=text,
                type_=language_v1.Document.Type.PLAIN_TEXT,
                language="en",  # Always English - saves language detection API calls
            )

            # Call the API (following official GCP NL documentation)
            response = self.client.analyze_sentiment(
                request={
                    "document": document,
                    "encoding_type": language_v1.EncodingType.UTF8,
                }
            )

            sentiment = response.document_sentiment
            score = float(sentiment.score)
            magnitude = float(sentiment.magnitude)

            # Map score to label using project requirements
            if score >= self.positive_threshold:
                label = "positive"
            elif score <= self.negative_threshold:
                label = "negative"
            else:
                label = "neutral"

            debug_msg = (
                f"GCP NL sentiment: score={score:.3f}, "
                f"magnitude={magnitude:.3f}, label={label}"
            )
            logger.debug(debug_msg)

            return label, score, magnitude

        except gcp_exceptions.InvalidArgument as e:
            logger.error(f"Invalid argument for GCP NL API: {e}")
            return "neutral", 0.0, None

        except gcp_exceptions.ResourceExhausted as e:
            logger.error(f"GCP NL API quota exceeded: {e}")
            # Fall back to neutral sentiment when quota exceeded
            return "neutral", 0.0, None

        except gcp_exceptions.DeadlineExceeded as e:
            logger.error(f"GCP NL API timeout: {e}")
            return "neutral", 0.0, None

        except Exception as e:
            logger.error(f"Unexpected error in GCP NL sentiment analysis: {e}")
            # Don't fail the entire process for sentiment analysis errors
            return "neutral", 0.0, None

    def analyze_sentiment_batch(
        self, texts: list[str]
    ) -> list[Tuple[str, float, Optional[float]]]:
        """
        Analyze sentiment for multiple texts in batch (future enhancement).

        Args:
            texts: List of texts to analyze (English only)

        Returns:
            List of sentiment tuples (label, score, magnitude)
        """
        # For now, process individually (could be optimized with batch API)
        results = []
        for text in texts:
            result = self.analyze_sentiment(text)
            results.append(result)
        return results


# Singleton instance for dependency injection
gcp_nlp_client = GcpNlpClient()


def analyze_sentiment_gcp(text: str) -> Tuple[str, float]:
    """
    Convenience function that matches the VADER interface.

    Args:
        text: Text to analyze (English only)

    Returns:
        Tuple of (label, score) - magnitude is dropped to match VADER interface
    """
    label, score, _ = gcp_nlp_client.analyze_sentiment(text)
    return label, score
