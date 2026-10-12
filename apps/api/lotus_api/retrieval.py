import re
from collections.abc import Iterable

from .fixtures import load_fixture
from .models import AuthContext, ChatRequest, Evidence, Scope

TOKEN = re.compile(r"[a-z0-9]+")
JIRA_KEY = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "do",
    "for",
    "how",
    "is",
    "of",
    "on",
    "the",
    "to",
    "what",
    "when",
    "why",
    "with",
}


def tokens(value: str) -> set[str]:
    return {token for token in TOKEN.findall(value.casefold()) if token not in STOP_WORDS}


def _scope(auth: AuthContext, request: ChatRequest) -> Scope:
    return Scope(
        tenant_id=auth.tenant_id,
        project_id=request.project_id,
        meeting_id=request.meeting_id,
        repository_id=request.repository_id,
    )


def _authorized(row: dict, auth: AuthContext, request: ChatRequest) -> bool:
    if row["tenant_id"] != auth.tenant_id or row.get("project_id") != request.project_id:
        return False
    return bool(set(row.get("acl_principals", ())) & set(auth.principals))


def _evidence(
    row: dict,
    request: ChatRequest,
    auth: AuthContext,
    method: str,
    score: float,
) -> Evidence:
    return Evidence(
        source_id=row["source_id"],
        source_system=row["source_system"],
        source_type=row["source_type"],
        title=row.get("title"),
        uri=row.get("source_uri"),
        snippet=row["chunk_text"],
        section=row.get("section_path"),
        updated_at=row.get("source_updated_at"),
        retrieval_method=method,
        scope=_scope(auth, request),
        score=round(score, 4),
        version=row.get("source_version"),
    )


def exact_jira(request: ChatRequest, auth: AuthContext) -> list[Evidence]:
    match = JIRA_KEY.search(request.message)
    if not match:
        return []
    key = match.group(0)
    for row in load_fixture("jira/issues.json"):
        if row["source_id"] == key and _authorized(row, auth, request):
            return [_evidence(row, request, auth, "demo_fixture", 1.0)]
    return []


def semantic_search(request: ChatRequest, auth: AuthContext, top_k: int = 8) -> list[Evidence]:
    query_tokens = tokens(request.message)
    candidates: list[tuple[float, dict]] = []
    for fixture in ("product/chunks.json", "technical/chunks.json"):
        for row in load_fixture(fixture):
            if not _authorized(row, auth, request):
                continue
            document_tokens = tokens(" ".join((row.get("title", ""), row["chunk_text"])))
            overlap = query_tokens & document_tokens
            if not overlap or len(overlap) < min(2, len(query_tokens)):
                continue
            score = len(overlap) / max(1, len(query_tokens))
            candidates.append((score, row))
    candidates.sort(key=lambda item: (-item[0], item[1]["source_id"]))
    return [
        _evidence(row, request, auth, "demo_fixture", score) for score, row in candidates[:top_k]
    ]


def unique_sources(items: Iterable[Evidence]) -> list[Evidence]:
    seen: set[str] = set()
    result: list[Evidence] = []
    for item in items:
        if item.source_id in seen:
            continue
        seen.add(item.source_id)
        result.append(item)
    return result
