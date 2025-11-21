from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from ..utils.secrets import get_secret_or_env


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
    def db_password(self) -> str:
        """Get database password from Secret Manager or environment variable."""
        return (
            get_secret_or_env(
                secret_name="db-password", env_var="POSTGRES_PASSWORD", default=""
            )
            or ""
        )

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.env == "local":
            return self.local_database_url

        # For production, use the configured database URL
        return self.database_url
