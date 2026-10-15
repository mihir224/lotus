from collections import defaultdict
from datetime import UTC, datetime
from uuid import uuid4

from .models import (
    AuthContext,
    DocCatalogResponse,
    DocPageDetail,
    DocSearchHit,
    DocSourceCreate,
    DocSourceSummary,
    DocTeamGroup,
)
from .storage.base import KnowledgeStore


def _chunk_rows(store: KnowledgeStore, auth: AuthContext, project_id: str) -> list[dict]:
    return store.list_knowledge_document_chunks(auth, project_id)


def _aggregate(rows: list[dict]) -> dict[str, dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["source_id"]].append(row)
    aggregated: dict[str, dict] = {}
    for source_id, chunks in grouped.items():
        chunks.sort(key=lambda item: (item.get("section_path") or "", item["chunk_id"]))
        primary = chunks[0]
        updated = max(
            (item.get("source_updated_at") for item in chunks if item.get("source_updated_at")),
            default=None,
        )
        body = "\n\n".join(
            item["chunk_text"].strip()
            for item in chunks
            if item["chunk_text"].strip()
        )
        aggregated[source_id] = {
            "source_id": source_id,
            "title": primary["title"],
            "team": primary["team"],
            "source_type": primary["source_type"],
            "source_system": primary["source_system"],
            "source_uri": primary.get("source_uri"),
            "updated_at": updated,
            "body": body,
        }
    return aggregated


def _format_updated(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _summary(entry: dict) -> DocSourceSummary:
    return DocSourceSummary(
        source_id=entry["source_id"],
        title=entry["title"],
        team=entry["team"],
        source_type=entry["source_type"],
        source_system=entry["source_system"],
        updated_at=_format_updated(entry.get("updated_at")),
    )


def get_docs_catalog(
    store: KnowledgeStore,
    auth: AuthContext,
    project_id: str,
) -> DocCatalogResponse:
    aggregated = _aggregate(_chunk_rows(store, auth, project_id))
    by_team: dict[str, list[DocSourceSummary]] = defaultdict(list)
    for entry in aggregated.values():
        by_team[entry["team"]].append(_summary(entry))
    groups = [
        DocTeamGroup(team=team, pages=sorted(pages, key=lambda page: page.title.casefold()))
        for team, pages in sorted(by_team.items(), key=lambda item: item[0].casefold())
    ]
    return DocCatalogResponse(project_id=project_id, groups=groups)


def get_doc_page(
    store: KnowledgeStore,
    auth: AuthContext,
    project_id: str,
    source_id: str,
) -> DocPageDetail:
    aggregated = _aggregate(_chunk_rows(store, auth, project_id))
    entry = aggregated.get(source_id)
    if entry is None:
        raise LookupError(source_id)
    return DocPageDetail(
        source_id=entry["source_id"],
        project_id=project_id,
        title=entry["title"],
        team=entry["team"],
        source_type=entry["source_type"],
        source_system=entry["source_system"],
        source_uri=entry.get("source_uri"),
        body=entry["body"],
        updated_at=_format_updated(entry.get("updated_at")),
    )


def search_docs(
    store: KnowledgeStore,
    auth: AuthContext,
    project_id: str,
    query: str,
) -> list[DocSearchHit]:
    needle = query.strip().casefold()
    if not needle:
        return []
    aggregated = _aggregate(_chunk_rows(store, auth, project_id))
    hits: list[DocSearchHit] = []
    for entry in aggregated.values():
        title = entry["title"]
        body = entry["body"]
        haystack = f"{title}\n{body}".casefold()
        if needle not in haystack and needle not in entry["source_id"].casefold():
            continue
        snippet = body
        index = haystack.find(needle)
        if index >= 0:
            start = max(0, index - 40)
            end = min(len(body), index + len(needle) + 80)
            snippet = body[start:end].strip()
            if start > 0:
                snippet = f"…{snippet}"
            if end < len(body):
                snippet = f"{snippet}…"
        elif len(snippet) > 160:
            snippet = f"{snippet[:160]}…"
        hits.append(
            DocSearchHit(
                source_id=entry["source_id"],
                title=title,
                team=entry["team"],
                source_type=entry["source_type"],
                snippet=snippet,
                updated_at=_format_updated(entry.get("updated_at")),
            )
        )
    hits.sort(key=lambda item: item.title.casefold())
    return hits


def create_doc_source(
    store: KnowledgeStore,
    auth: AuthContext,
    payload: DocSourceCreate,
) -> DocPageDetail:
    title = payload.title.strip()
    body = payload.body.strip()
    if not title or not body:
        raise ValueError("Title and body are required")
    source_id = f"LOTUS-{uuid4().hex[:8].upper()}"
    chunk_id = f"{source_id}-001"
    now = datetime.now(UTC)
    row = {
        "chunk_id": chunk_id,
        "tenant_id": auth.tenant_id,
        "project_id": payload.project_id,
        "team": payload.team.strip(),
        "source_system": "lotus",
        "source_type": payload.source_type,
        "source_id": source_id,
        "source_uri": f"lotus://docs/{source_id}",
        "title": title,
        "section_path": "Overview",
        "chunk_text": body,
        "acl_principals": list(auth.principals),
        "metadata": {},
        "source_version": "1",
        "source_updated_at": now,
    }
    store.upsert_knowledge_document_chunk(auth, row)
    return DocPageDetail(
        source_id=source_id,
        project_id=payload.project_id,
        title=title,
        team=payload.team.strip(),
        source_type=payload.source_type,
        source_system="lotus",
        source_uri=row["source_uri"],
        body=body,
        updated_at=now.isoformat(),
    )
