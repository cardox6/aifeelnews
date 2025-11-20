from .crawler import CrawlerConfig
from .database import DatabaseConfig
from .ingestion import IngestionConfig
from .scheduler import SchedulerConfig
from .ui import UIConfig


class AppConfig:
    def __init__(self) -> None:
        self.database = DatabaseConfig()
        self.ingestion = IngestionConfig()
        self.crawler = CrawlerConfig()
        self.scheduler = SchedulerConfig()
        self.ui = UIConfig()

    @property
    def env(self) -> str:
        return self.database.env

    @property
    def sqlalchemy_database_url(self) -> str:
        return self.database.sqlalchemy_database_url


config = AppConfig()


class LegacySettings:
    def __init__(self, app_config: AppConfig) -> None:
        self._config = app_config

    @property
    def ENV(self) -> str:
        return self._config.database.env

    @property
    def LOCAL_DATABASE_URL(self) -> str:
        return self._config.database.local_database_url

    @property
    def DATABASE_URL(self) -> str:
        return self._config.database.database_url

    @property
    def SQLALCHEMY_DATABASE_URL(self) -> str:
        return self._config.database.sqlalchemy_database_url

    @property
    def MEDIASTACK_BASE_URL(self) -> str:
        return self._config.ingestion.mediastack_base_url

    @property
    def MEDIASTACK_API_KEY(self) -> str:
        return self._config.ingestion.mediastack_api_key

    @property
    def MEDIASTACK_FETCH_LIMIT(self) -> int:
        return self._config.ingestion.mediastack_fetch_limit

    @property
    def MEDIASTACK_SORT(self) -> str:
        return self._config.ingestion.mediastack_sort

    @property
    def MEDIASTACK_FETCH_CATEGORIES(self) -> str:
        return self._config.ingestion.mediastack_fetch_categories

    @property
    def MEDIASTACK_LANGUAGES(self) -> str:
        return self._config.ingestion.mediastack_languages

    @property
    def MEDIASTACK_TIMEOUT(self) -> int:
        return self._config.ingestion.mediastack_timeout

    @property
    def ARTICLE_CONTENT_TTL_HOURS(self) -> int:
        return self._config.ingestion.article_content_ttl_hours

    @property
    def CRAWLER_USER_AGENT(self) -> str:
        return self._config.crawler.crawler_user_agent

    @property
    def CRAWLER_DEFAULT_DELAY(self) -> float:
        return self._config.crawler.crawler_default_delay

    @property
    def CRAWLER_MAX_CONCURRENT_DOMAINS(self) -> int:
        return self._config.crawler.crawler_max_concurrent_domains

    @property
    def CRAWLER_REQUEST_TIMEOUT(self) -> int:
        return self._config.crawler.crawler_request_timeout

    @property
    def CRAWLER_ROBOTS_CACHE_HOURS(self) -> int:
        return self._config.crawler.crawler_robots_cache_hours

    @property
    def PLACEHOLDER_IMAGE(self) -> str:
        return self._config.ui.placeholder_image


settings = LegacySettings(config)
