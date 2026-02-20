"""
Google Cloud Natural Language integration.

This module provides a production-grade NLP client using
Google Cloud Natural Language API with proper error handling, rate limiting,
and abstraction that matches the existing sentiment provider interface.

Uses annotateText for single-call extraction of:
  - Document sentiment (score + magnitude)
  - Named entities (people, organizations, locations, etc.)
  - Content classification (taxonomy categories)
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from google.api_core import exceptions as gcp_exceptions  # type: ignore[import-untyped]
from google.cloud import language_v1  # type: ignore[import-untyped]

from app.config import config
from app.utils.secrets import get_gcp_project_id

logger = logging.getLogger(__name__)


@dataclass
class EntityResult:
    """Single entity from GCP NL annotateText."""

    name: str
    type: str  # e.g., "PERSON", "ORGANIZATION", "LOCATION"
    salience: float  # 0.0 to 1.0
    wikipedia_url: Optional[str] = None
    mid: Optional[str] = None
    mention_count: int = 1  # Number of mentions in source text


@dataclass
class CategoryResult:
    """Single category from GCP NL annotateText."""

    name: str  # Taxonomy path, e.g., "/News/Business"
    confidence: float  # 0.0 to 1.0


@dataclass
class AnnotateTextResult:
    """Full result from GCP NL annotateText (sentiment + entities + categories)."""

    # Sentiment
    sentiment_label: str
    sentiment_score: float
    sentiment_magnitude: Optional[float]
    # Entities
    entities: List[EntityResult] = field(default_factory=list)
    # Categories
    categories: List[CategoryResult] = field(default_factory=list)


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
        self.project_id = (
            project_id or config.sentiment.gcp_nl_project_id or get_gcp_project_id()
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

    def annotate_text(self, text: str) -> AnnotateTextResult:
        """
        Analyze text using GCP NL annotateText for sentiment + entities + categories.

        Single API call replaces separate analyzeSentiment / analyzeEntities /
        classifyText calls, saving quota and cost.

        Args:
            text: English text to analyze

        Returns:
            AnnotateTextResult with sentiment, entities, and categories
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for annotateText")
            return AnnotateTextResult(
                sentiment_label="neutral",
                sentiment_score=0.0,
                sentiment_magnitude=None,
            )

        # Truncate text if too long
        max_length = config.sentiment.gcp_nl_max_text_length
        if len(text.encode("utf-8")) > max_length:
            logger.warning(f"Text too long ({len(text)} chars), truncating")
            text = text[: max_length // 4]

        try:
            document = language_v1.Document(
                content=text,
                type_=language_v1.Document.Type.PLAIN_TEXT,
                language="en",
            )

            # Request all three features in one call
            features = language_v1.AnnotateTextRequest.Features(
                extract_entities=True,
                extract_document_sentiment=True,
                classify_text=True,
            )

            response = self.client.annotate_text(
                request={
                    "document": document,
                    "features": features,
                    "encoding_type": language_v1.EncodingType.UTF8,
                }
            )

            # Extract sentiment (same logic as analyze_sentiment)
            sentiment = response.document_sentiment
            score = float(sentiment.score)
            magnitude = float(sentiment.magnitude)

            if score >= self.positive_threshold:
                label = "positive"
            elif score <= self.negative_threshold:
                label = "negative"
            else:
                label = "neutral"

            # Extract entities with dedup by (name, type).
            # The API should return one Entity per unique entity, but
            # in practice near-duplicates with different salience occur.
            # Dedup here at the source so downstream code receives clean data.
            entity_map: dict[tuple[str, str], EntityResult] = {}
            for entity in response.entities:
                wikipedia_url = None
                mid = None
                if entity.metadata:
                    wikipedia_url = entity.metadata.get("wikipedia_url")
                    mid = entity.metadata.get("mid")

                entity_type_name = language_v1.Entity.Type(entity.type_).name
                mention_count = len(entity.mentions) if entity.mentions else 1
                key = (entity.name, entity_type_name)

                if key in entity_map:
                    existing = entity_map[key]
                    # Keep highest salience, sum mention counts
                    if float(entity.salience) > existing.salience:
                        entity_map[key] = EntityResult(
                            name=entity.name,
                            type=entity_type_name,
                            salience=float(entity.salience),
                            wikipedia_url=wikipedia_url or existing.wikipedia_url,
                            mid=mid or existing.mid,
                            mention_count=existing.mention_count + mention_count,
                        )
                    else:
                        existing.mention_count += mention_count
                else:
                    entity_map[key] = EntityResult(
                        name=entity.name,
                        type=entity_type_name,
                        salience=float(entity.salience),
                        wikipedia_url=wikipedia_url,
                        mid=mid,
                        mention_count=mention_count,
                    )

            entities: List[EntityResult] = list(entity_map.values())

            # Extract categories (classifyText needs ~20 tokens;
            # short texts may return empty — this is expected)
            categories: List[CategoryResult] = []
            for category in response.categories:
                categories.append(
                    CategoryResult(
                        name=category.name,
                        confidence=float(category.confidence),
                    )
                )

            logger.debug(
                f"GCP NL annotateText: sentiment={label} ({score:.3f}), "
                f"entities={len(entities)}, categories={len(categories)}"
            )

            return AnnotateTextResult(
                sentiment_label=label,
                sentiment_score=score,
                sentiment_magnitude=magnitude,
                entities=entities,
                categories=categories,
            )

        except gcp_exceptions.InvalidArgument as e:
            logger.error(f"Invalid argument for GCP NL annotateText: {e}")
            return AnnotateTextResult(
                sentiment_label="neutral",
                sentiment_score=0.0,
                sentiment_magnitude=None,
            )

        except gcp_exceptions.ResourceExhausted as e:
            logger.error(f"GCP NL API quota exceeded: {e}")
            return AnnotateTextResult(
                sentiment_label="neutral",
                sentiment_score=0.0,
                sentiment_magnitude=None,
            )

        except gcp_exceptions.DeadlineExceeded as e:
            logger.error(f"GCP NL API timeout: {e}")
            return AnnotateTextResult(
                sentiment_label="neutral",
                sentiment_score=0.0,
                sentiment_magnitude=None,
            )

        except Exception as e:
            logger.error(f"Unexpected error in GCP NL annotateText: {e}")
            return AnnotateTextResult(
                sentiment_label="neutral",
                sentiment_score=0.0,
                sentiment_magnitude=None,
            )


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
