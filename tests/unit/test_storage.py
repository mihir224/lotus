import pytest
from lotus_api.config import Settings
from lotus_api.embeddings import DeterministicEmbedder
from lotus_api.models import AuthContext
from lotus_api.storage.factory import get_store
from lotus_api.storage.memory import MemoryKnowledgeStore
from lotus_api.storage.postgres import PostgresKnowledgeStore


def test_seed_is_idempotent_and_enforces_tenant_scope() -> None:
    settings = Settings(store_backend="memory")
    store = MemoryKnowledgeStore(settings, DeterministicEmbedder())
    first = store.seed()
    second = store.seed()
    assert first == second == {
        "documents": 90,
        "meetings": 13,
        "calendar_events": 10,
        "board_issues": 30,
        "employees": 6,
        "projects": 3,
    }
    unauthorized = AuthContext(tenant_id="other", user_id="x", principals=("group:demo",))
    assert store.search_documents("checkout retry", unauthorized, "payments") == []
    assert store.search_transcripts("retry jitter", unauthorized, "payments") == []


def test_cloud_sql_uses_secret_backed_unix_socket_url() -> None:
    settings = Settings(
        store_backend="postgres",
        cloud_sql_instance="project:region:instance",
        db_user="lotus_app",
        db_name="lotus",
        db_password="not-logged",
    )
    store = PostgresKnowledgeStore(settings, DeterministicEmbedder())
    assert store.engine.url.username == "lotus_app"
    assert store.engine.url.database == "lotus"
    assert store.engine.url.query["host"] == "/cloudsql/project:region:instance"
    assert "not-logged" not in store.engine.url.render_as_string(hide_password=True)


def test_cloud_sql_requires_database_password() -> None:
    settings = Settings(
        store_backend="postgres",
        cloud_sql_instance="project:region:instance",
        db_password=None,
    )
    with pytest.raises(ValueError, match="DB_PASSWORD"):
        PostgresKnowledgeStore(settings, DeterministicEmbedder())


def test_unknown_store_backend_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(store_backend="postgress")
    monkeypatch.setattr("lotus_api.storage.factory.get_settings", lambda: settings)
    get_store.cache_clear()
    with pytest.raises(ValueError, match="Unsupported STORE_BACKEND"):
        get_store()
    get_store.cache_clear()
