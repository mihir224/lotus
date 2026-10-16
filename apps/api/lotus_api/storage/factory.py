from functools import lru_cache

from ..config import get_settings
from ..embeddings import build_embedder
from .base import KnowledgeStore
from .memory import MemoryKnowledgeStore
from .postgres import PostgresKnowledgeStore


@lru_cache
def get_store() -> KnowledgeStore:
    settings = get_settings()
    embedder = build_embedder(settings)
    if settings.store_backend == "postgres":
        return PostgresKnowledgeStore(settings, embedder)
    if settings.store_backend == "memory":
        return MemoryKnowledgeStore(settings, embedder)
    raise ValueError(f"Unsupported STORE_BACKEND: {settings.store_backend}")
