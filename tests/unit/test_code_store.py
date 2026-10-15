from pathlib import Path

import pytest
from lotus_api.code_store import MockCodeStore
from lotus_api.models import AuthContext


@pytest.fixture
def code_store() -> MockCodeStore:
    return MockCodeStore(Path("demo_data"))


def test_code_search_returns_file_line_citations(code_store: MockCodeStore) -> None:
    auth = AuthContext(tenant_id="demo", user_id="alice", principals=("group:demo",))
    evidence = code_store.search("full jitter retry", auth, "payments")
    assert evidence
    assert any("#L" in (row.uri or "") for row in evidence)
    assert all(row.scope.tenant_id == "demo" for row in evidence)


def test_code_store_rejects_traversal_and_unauthorized_repositories(
    code_store: MockCodeStore,
) -> None:
    auth = AuthContext(tenant_id="demo", user_id="alice", principals=("group:demo",))
    with pytest.raises(ValueError, match="Invalid"):
        code_store.read_file("checkout-service", "../secret", auth, "payments")
    with pytest.raises(PermissionError, match="unauthorized"):
        code_store.read_file("private-ledger", "ledger.py", auth, "payments")
