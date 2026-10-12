from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "lotus-api"
    google_cloud_project: str | None = None
    google_cloud_location: str = "us-central1"
    demo_mode: bool = True
    fixture_dir: Path = Path("demo_data")
    max_evidence_items: int = 8


@lru_cache
def get_settings() -> Settings:
    return Settings()
