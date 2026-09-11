from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="MOCKZOHO_",
        extra="ignore",
    )

    host: str = "0.0.0.0"
    port: int = 8090

    database_url: str = f"sqlite:///{PROJECT_ROOT / 'mockzoho.db'}"
    seed_dir: Path = PROJECT_ROOT / "seeds"
    seed_on_startup: bool = True
    reset_db_on_startup: bool = False

    api_domain: str = "http://localhost:8090"
    timezone_offset: str = "+08:00"

    token_ttl_seconds: int = 3600
    expected_client_id: str | None = None
    expected_client_secret: str | None = None
    expected_refresh_token: str | None = None

    rate_limit_credits: int = 5000
    rate_limit_window_seconds: int = 60

    request_log_size: int = 200
    max_records_per_write: int = 100
    max_per_page: int = 200
    default_per_page: int = 200



@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
