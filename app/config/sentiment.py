"""
Sentiment analysis configuration.

This module defines configuration for sentiment analysis providers,
including Google Cloud Natural Language API and VADER sentiment.
"""

from typing import Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class SentimentConfig(BaseSettings):
    """Configuration for sentiment analysis providers."""

    # Provider selection - GCP_NL for production, VADER fallback available
    sentiment_provider: Literal["VADER", "GCP_NL"] = Field(
        default="GCP_NL", description="Sentiment analysis provider to use"
    )

    # VADER Configuration (Official thresholds from VADER documentation)
    vader_positive_threshold: float = Field(
        default=0.05,
        description="Threshold for positive sentiment in VADER (official: >= 0.05)",
    )
    vader_negative_threshold: float = Field(
        default=-0.05,
        description="Threshold for negative sentiment in VADER (official: <= -0.05)",
    )

    # Google Cloud Natural Language Configuration
    gcp_nl_positive_threshold: float = Field(
        default=0.25,
        description="Threshold for positive sentiment in GCP NL",
    )
    gcp_nl_negative_threshold: float = Field(
        default=-0.25,
        description="Threshold for negative sentiment in GCP NL",
    )

    gcp_nl_project_id: Optional[str] = Field(
        default=None, description="Google Cloud project ID for Natural Language API"
    )

    gcp_nl_max_text_length: int = Field(
        default=1000000, description="Maximum text length for GCP NL API (bytes)"
    )

    # Fallback Configuration
    enable_fallback: bool = Field(
        default=True, description="Enable fallback to VADER if GCP NL fails"
    )

    # Language Detection
    default_language: str = Field(
        default="en", description="Default language code for sentiment analysis"
    )

    supported_languages: list[str] = Field(
        default=[
            "en",
            "es",
            "fr",
            "de",
            "it",
            "pt",
            "ru",
            "ja",
            "ko",
            "zh",
            "ar",
            "hi",
        ],
        description="List of supported language codes",
    )

    class Config:
        env_prefix = ""
        case_sensitive = False


# Default instance
sentiment_config = SentimentConfig()
