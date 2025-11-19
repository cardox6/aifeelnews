from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # switch: "local" or "production"
    ENV: str = "local"
    # local database
    LOCAL_DATABASE_URL: str = ""
    # production / Docker database
    DATABASE_URL: str = ""
    # Mediastack API
    MEDIASTACK_BASE_URL: str = "https://api.mediastack.com/v1/news"
    MEDIASTACK_API_KEY: str = ""
    MEDIASTACK_FETCH_LIMIT: int = 25
    MEDIASTACK_SORT: str = "published_desc"
    MEDIASTACK_FETCH_CATEGORIES: str = (
        "general,business,health,science,technology,-sports,-entertainment"
    )
    MEDIASTACK_LANGUAGES: str = "en"
    MEDIASTACK_TIMEOUT: int = 10

    # Article content TTL (Time To Live) in hours for data minimisation compliance
    # Content older than 7 days (168 hours) will be automatically removed
    ARTICLE_CONTENT_TTL_HOURS: int = 168  # 7 days = 7 * 24 = 168 hours

    # Web crawling configuration for ethical compliance
    CRAWLER_USER_AGENT: str = "aifeelnews-bot/1.0 (+https://github.com/cardox6/aifeelnews; contact@aifeelnews.com)"
    CRAWLER_DEFAULT_DELAY: float = 1.0  # Default delay between requests (seconds)
    CRAWLER_MAX_CONCURRENT_DOMAINS: int = 3  # Max concurrent crawling per domain
    CRAWLER_REQUEST_TIMEOUT: int = 30  # HTTP request timeout
    CRAWLER_ROBOTS_CACHE_HOURS: int = 24  # Cache robots.txt for 24 hours

    PLACEHOLDER_IMAGE: str = "https://picsum.photos/id/366/200/300"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def SQLALCHEMY_DATABASE_URL(self) -> str:
        if self.ENV == "local":
            return self.LOCAL_DATABASE_URL
        return self.DATABASE_URL


settings = Settings()
