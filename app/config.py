from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # switch: "local" or "production"
    ENV: str = Field("local", env="ENV")
    # local database
    LOCAL_DATABASE_URL: str = Field(..., env="LOCAL_DATABASE_URL")
    # production / Docker database
    DATABASE_URL: str = Field(..., env="DATABASE_URL")
    # Mediastack API
    MEDIASTACK_BASE_URL: str = Field(
        "https://api.mediastack.com/v1/news", env="MEDIASTACK_BASE_URL"
    )
    MEDIASTACK_API_KEY: str = Field(..., env="MEDIASTACK_API_KEY")
    MEDIASTACK_FETCH_LIMIT: int = Field(25, env="MEDIASTACK_FETCH_LIMIT")
    MEDIASTACK_SORT: str = Field("published_desc", env="MEDIASTACK_SORT")
    MEDIASTACK_FETCH_CATEGORIES: str = Field(
        "general,business,health,science,technology,-sports,-entertainment",
        env="MEDIASTACK_FETCH_CATEGORIES",
    )
    MEDIASTACK_LANGUAGES: str = Field("en", env="MEDIASTACK_LANGUAGES")
    MEDIASTACK_TIMEOUT: int = Field(10, env="MEDIASTACK_TIMEOUT")

    PLACEHOLDER_IMAGE: str = Field(
        "https://picsum.photos/id/366/200/300", env="PLACEHOLDER_IMAGE"
    )

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
