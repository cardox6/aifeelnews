from pydantic_settings import BaseSettings, SettingsConfigDict


class IngestionConfig(BaseSettings):
    mediastack_base_url: str = "https://api.mediastack.com/v1/news"
    mediastack_api_key: str = ""
    mediastack_fetch_limit: int = 25
    mediastack_sort: str = "published_desc"
    mediastack_fetch_categories: str = (
        "general,business,health,science,technology,-sports,-entertainment"
    )
    mediastack_languages: str = "en"
    mediastack_timeout: int = 10
    article_content_ttl_hours: int = 168

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
