from pydantic_settings import BaseSettings, SettingsConfigDict


class CrawlerConfig(BaseSettings):
    crawler_user_agent: str = (
        "aifeelnews-bot/1.0 "
        "(+https://github.com/cardox6/aifeelnews; matias.cardone@code.berlin)"
    )
    crawler_default_delay: float = 1.0
    crawler_max_concurrent_domains: int = 3
    crawler_request_timeout: int = 30
    crawler_robots_cache_hours: int = 24

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
