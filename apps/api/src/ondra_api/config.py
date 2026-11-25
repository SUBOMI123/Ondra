from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Read from the environment (and a repo-root .env in development). See .env.example."""

    model_config = SettingsConfigDict(env_file=("../../.env", ".env"), extra="ignore")

    database_url: str = "postgresql+asyncpg://ondra_app:ondra_app_dev@localhost:5432/ondra"
    migrations_database_url: str = "postgresql+asyncpg://ondra_owner:ondra_owner_dev@localhost:5432/ondra"
    jwt_secret: str = "dev-only-change-me-dev-only-change-me"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    app_base_url: str = "http://localhost:3001"

    @property
    def cookie_secure(self) -> bool:
        return self.app_base_url.startswith("https://")


@lru_cache
def get_settings() -> Settings:
    return Settings()
