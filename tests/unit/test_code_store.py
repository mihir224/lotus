from pathlib import Path

import pytest
from lotus_api.code_store import CodeStore
from lotus_api.models import AuthContext


@pytest.fixture
def code_store() -> CodeStore:
    return CodeStore(Path("demo_data"))


def test_code_search_returns_file_line_citations(code_store: CodeStore) -> None:
    auth = AuthContext(tenant_id="demo", user_id="alice", principals=("group:demo",))
    evidence = code_store.search("full jitter retry", auth, "payments")
    assert evidence
    assert any("#L" in (row.uri or "") for row in evidence)
    assert all(row.scope.tenant_id == "demo" for row in evidence)
    assert len({(row.section or "").split(":", 1)[0] for row in evidence}) == len(evidence)


def test_code_search_includes_bounded_neighboring_lines(code_store: CodeStore) -> None:
    auth = AuthContext(tenant_id="demo", user_id="alice", principals=("group:demo",))
    evidence = code_store.search(
        "where is full-jitter retry implemented and how many payment attempts are made",
        auth,
        "payments",
        repository_id="checkout-service",
    )

    checkout = next(row for row in evidence if "src/checkout.py" in (row.section or ""))
    assert "for attempt in range(3)" in checkout.snippet
    assert len(checkout.snippet) <= 2_000


def test_code_store_rejects_traversal_and_unauthorized_repositories(
    code_store: CodeStore,
) -> None:
    auth = AuthContext(tenant_id="demo", user_id="alice", principals=("group:demo",))
    with pytest.raises(ValueError, match="Invalid"):
        code_store.read_file("checkout-service", "../secret", auth, "payments")
    with pytest.raises(PermissionError, match="unauthorized"):
        code_store.read_file("private-ledger", "ledger.py", auth, "payments")
