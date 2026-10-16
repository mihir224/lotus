import json
from pathlib import PurePosixPath
from typing import Any

from .models import AuthContext, Evidence, Scope


class CodeStore:
    """Read-only, ACL-aware repository adapter backed by demo data."""

    def __init__(self, fixture_dir):
        self.repositories: list[dict[str, Any]] = json.loads(
            (fixture_dir / "code/repositories.json").read_text(encoding="utf-8")
        )

    def _authorized(self, auth: AuthContext, project_id: str) -> list[dict[str, Any]]:
        principals = set(auth.principals)
        return [
            repo
            for repo in self.repositories
            if repo["tenant_id"] == auth.tenant_id
            and repo["project_id"] == project_id
            and principals.intersection(repo["acl_principals"])
        ]

    @staticmethod
    def _safe_path(path: str) -> str:
        candidate = PurePosixPath(path)
        if candidate.is_absolute() or ".." in candidate.parts or not candidate.parts:
            raise ValueError("Invalid repository path")
        return candidate.as_posix()

    def list_repositories(self, auth: AuthContext, project_id: str) -> list[dict[str, str]]:
        return [
            {"repository_id": repo["repository_id"], "name": repo["name"]}
            for repo in self._authorized(auth, project_id)
        ]

    def list_tree(self, repository_id: str, auth: AuthContext, project_id: str) -> list[str]:
        repo = self._repository(repository_id, auth, project_id)
        return sorted(repo["files"])[:200]

    def read_file(self, repository_id: str, path: str, auth: AuthContext, project_id: str) -> str:
        safe_path = self._safe_path(path)
        repo = self._repository(repository_id, auth, project_id)
        if safe_path not in repo["files"]:
            raise FileNotFoundError(safe_path)
        return repo["files"][safe_path].encode("utf-8")[:16_384].decode("utf-8", "ignore")

    def search(
        self,
        query: str,
        auth: AuthContext,
        project_id: str,
        repository_id: str | None = None,
        limit: int = 8,
    ) -> list[Evidence]:
        terms = [term for term in query.casefold().split() if len(term) > 2]
        matches: list[tuple[int, Evidence]] = []
        for repo in self._authorized(auth, project_id):
            if repository_id and repo["repository_id"] != repository_id:
                continue
            for path, content in repo["files"].items():
                for line_number, line in enumerate(content.splitlines(), start=1):
                    score = sum(term in f"{path} {line}".casefold() for term in terms)
                    if score:
                        matches.append(
                            (
                                score,
                                Evidence(
                                    source_id=f"{repo['repository_id']}:{path}:{line_number}",
                                    source_system="github",
                                    source_type="code",
                                    title=f"{repo['name']} · {path}",
                                    uri=f"fixture://github/{repo['repository_id']}/{path}#L{line_number}",
                                    snippet=line[:500],
                                    section=f"{path}:{line_number}",
                                    retrieval_method="repository_search",
                                    scope=Scope(
                                        tenant_id=auth.tenant_id,
                                        project_id=project_id,
                                        repository_id=repo["repository_id"],
                                    ),
                                    score=float(score),
                                ),
                            )
                        )
        matches.sort(key=lambda item: (-item[0], item[1].source_id))
        return [evidence for _, evidence in matches[: min(limit, 20)]]

    def _repository(self, repository_id: str, auth: AuthContext, project_id: str) -> dict[str, Any]:
        for repo in self._authorized(auth, project_id):
            if repo["repository_id"] == repository_id:
                return repo
        raise PermissionError("Repository is unavailable or unauthorized")
