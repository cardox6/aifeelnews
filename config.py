from pydantic import BaseSettings, Field

class Settings(BaseSettings):
    # switch: "local" or "production"
    ENV: str = Field("local", env="ENV")

    # local database
    LOCAL_DATABASE_URL: str = Field(..., env="LOCAL_DATABASE_URL")
    # production / Docker database
    DATABASE_URL: str = Field(..., env="DATABASE_URL")
    
    # Mediastack API
    MEDIASTACK_API_KEY: str = Field(..., env="MEDIASTACK_API_KEY")
    MEDIASTACK_BASE_URL: str = Field("https://api.mediastack.com/v1/news", env="MEDIASTACK_BASE_URL")

    # filtering & pagination
    LANGUAGES: str = Field("en", env="LANGUAGES")
    CATEGORIES: str = Field("general,business,health,science,technology,-sports,-entertainment", env="CATEGORIES")
    PAGESIZE: int = Field(25, env="PAGESIZE")

    # Fallback for articles that lack an image
    PLACEHOLDER_IMAGE: str = Field(
        "https://picsum.photos/id/366/200/300",
        env="PLACEHOLDER_IMAGE"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def SQLALCHEMY_DATABASE_URL(self) -> str:
        return (
            self.LOCAL_DATABASE_URL
            if self.ENV.lower() == "local"
            else self.DATABASE_URL
        )


settings = Settings()
