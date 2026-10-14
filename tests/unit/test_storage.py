from lotus_api.config import Settings
from lotus_api.embeddings import DeterministicEmbedder
from lotus_api.models import AuthContext
from lotus_api.storage.memory import MemoryKnowledgeStore


def test_seed_is_idempotent_and_enforces_tenant_scope() -> None:
    settings = Settings(store_backend="memory")
    store = MemoryKnowledgeStore(settings, DeterministicEmbedder())
    first = store.seed()
    second = store.seed()
    assert first == second == {"documents": 12, "meetings": 13}
    unauthorized = AuthContext(tenant_id="other", user_id="x", principals=("group:demo",))
    assert store.search_documents("checkout retry", unauthorized, "payments") == []
    assert store.search_transcripts("retry jitter", unauthorized, "payments") == []
