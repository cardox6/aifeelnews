from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    # switch: "local" or "production"
    ENV: str = Field("local", env="ENV")

    # local database
    LOCAL_DATABASE_URL: str = Field(..., env="LOCAL_DATABASE_URL")
    # production / Docker database
    DATABASE_URL: str = Field(..., env="DATABASE_URL")

    MEDIASTACK_API_KEY: str = Field(..., env="MEDIASTACK_API_KEY")

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
