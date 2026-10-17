import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "lotus-api"
    google_cloud_project: str | None = None
    google_cloud_location: str = "global"
    embedding_location: str = "global"
    demo_mode: bool = True
    runtime_mode: str = "fixture"
    embedding_runtime_mode: str = "fixture"
    store_backend: str = "memory"
    database_url: str = "postgresql+psycopg://lotus:lotus@localhost:5432/lotus"
    cloud_sql_instance: str | None = None
    db_user: str = "lotus_app"
    db_name: str = "lotus"
    db_password: str | None = None
    db_pool_size: int = 5
    db_max_overflow: int = 2
    db_pool_timeout_seconds: int = 10
    db_pool_recycle_seconds: int = 1800
    fixture_dir: Path = Path("demo_data")
    max_evidence_items: int = 8
    generation_model: str = "gemini-3.7-flash"
    router_model: str = "gemini-3.7-flash"
    embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = 768
    agent_timeout_seconds: float = 90.0
    web_agent_timeout_seconds: float = 180.0
    auth_mode: str = "dev"
    google_oauth_client_id: str | None = None
    agent_rate_limit_requests: int = 10
    agent_rate_limit_window_seconds: int = 300
    telemetry_enabled: bool = False
    mcp_base_url: str = ""
    display_timezone: str = "Asia/Kolkata"

    @property
    def internal_mcp_base_url(self) -> str:
        return self.mcp_base_url or f"http://127.0.0.1:{os.getenv('PORT', '8000')}"

    @property
    def active_embedding_model(self) -> str:
        if self.embedding_runtime_mode in {"agent_platform", "vertex"}:
            return f"agent-platform:{self.embedding_model}:{self.embedding_dimensions}"
        return f"fixture:hash-v1:{self.embedding_dimensions}"

    @property
    def database_connection_url(self) -> str | URL:
        if not self.cloud_sql_instance:
            return self.database_url
        if not self.db_password:
            raise ValueError("DB_PASSWORD is required when CLOUD_SQL_INSTANCE is configured")
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.db_user,
            password=self.db_password,
            database=self.db_name,
            query={"host": f"/cloudsql/{self.cloud_sql_instance}"},
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
