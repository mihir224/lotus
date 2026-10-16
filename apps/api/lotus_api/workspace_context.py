from .models import AuthContext, ChatRequest, Evidence
from .storage.base import KnowledgeStore


class WorkspaceContextResolver:
    """Resolve browser-selected IDs through authorized server-owned adapters."""

    def __init__(self, store: KnowledgeStore):
        self.store = store

    def resolve(self, request: ChatRequest, auth: AuthContext) -> list[Evidence]:
        selected = set(request.planning_item_ids + request.document_ids)
        resolved: list[Evidence] = []
        for source_id in selected:
            candidates = self.store.search_documents(source_id, auth, request.project_id, top_k=8)
            resolved.extend(row for row in candidates if row.source_id == source_id)
        return resolved
