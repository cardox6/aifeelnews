from typing import Tuple

from vaderSentiment.vaderSentiment import (
    SentimentIntensityAnalyzer,  # type: ignore[import-untyped]
)

# Thresholds
POSITIVE_THRESHOLD = 0.05
NEGATIVE_THRESHOLD = -0.05

analyzer = SentimentIntensityAnalyzer()


def analyze_sentiment(text: str) -> Tuple[str, float]:
    """Analyze sentiment of a given text using VADER."""
    if not text:
        return "neutral", 0.0

    score = analyzer.polarity_scores(text)["compound"]

    if score >= POSITIVE_THRESHOLD:
        return "positive", score
    elif score <= NEGATIVE_THRESHOLD:
        return "negative", score
    else:
        return "neutral", score
