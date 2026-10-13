from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "lotus-api"
    google_cloud_project: str | None = None
    google_cloud_location: str = "us-central1"
    demo_mode: bool = True
    runtime_mode: str = "fixture"
    store_backend: str = "memory"
    database_url: str = "postgresql+psycopg://lotus:lotus@localhost:5432/lotus"
    fixture_dir: Path = Path("demo_data")
    max_evidence_items: int = 8
    generation_model: str = "gemini-2.5-flash"
    router_model: str = "gemini-2.5-flash-lite"
    embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = 768

    @property
    def active_embedding_model(self) -> str:
        if self.runtime_mode == "vertex":
            return f"vertex:{self.embedding_model}:{self.embedding_dimensions}"
        return f"fixture:hash-v1:{self.embedding_dimensions}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
