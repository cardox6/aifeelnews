from pydantic_settings import BaseSettings, SettingsConfigDict


class UIConfig(BaseSettings):
    placeholder_image: str = "https://picsum.photos/id/366/200/300"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
