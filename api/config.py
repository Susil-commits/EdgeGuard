"""Application settings loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://edgeguard:edgeguard@db:5432/edgeguard"
    DB_ECHO: bool = False

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # Auth
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    # EDA webhook
    EDA_WEBHOOK_URL: str = "http://eda-runner:5000"

    # Agent
    AGENT_TOKEN_HASH: str = ""  # bcrypt hash of the shared agent token


settings = Settings()
