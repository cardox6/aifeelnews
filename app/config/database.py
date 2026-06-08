from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfig(BaseSettings):
    env: str = Field(default="local", alias="ENV")
    local_database_url: str = Field(default="", alias="LOCAL_DATABASE_URL")
    database_url: str = Field(default="", alias="DATABASE_URL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.env == "local":
            return self.local_database_url

        # For production, use the configured database URL
        return self.database_url
