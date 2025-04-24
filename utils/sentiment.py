from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

analyzer = SentimentIntensityAnalyzer()

def analyze_sentiment(text: str) -> tuple[str, float]:
    result = analyzer.polarity_scores(text)
    score = result["compound"]
    label = (
        "positive" if score > 0.05 else
        "negative" if score < -0.05 else
        "neutral"
    )
    return label, score
