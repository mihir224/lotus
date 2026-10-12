from lotus_api.models import AuthContext, ChatRequest
from lotus_api.retrieval import exact_jira, semantic_search

AUTH = AuthContext(tenant_id="demo", user_id="alice", principals=("user:alice", "group:demo"))


def test_exact_jira_uses_fixture() -> None:
    items = exact_jira(
        ChatRequest(message="Status of PAY-123?", project_id="payments"),
        AUTH,
    )
    assert [item.source_id for item in items] == ["PAY-123"]
    assert items[0].retrieval_method == "demo_fixture"


def test_semantic_search_keeps_product_and_technical_separate() -> None:
    items = semantic_search(
        ChatRequest(message="Why are checkout retries capped with jitter?", project_id="payments"),
        AUTH,
    )
    assert {item.source_type for item in items} >= {"product_doc", "adr"}


def test_cross_tenant_rows_are_not_returned() -> None:
    other = AUTH.model_copy(update={"tenant_id": "other"})
    items = semantic_search(
        ChatRequest(message="checkout retries", project_id="payments"),
        other,
    )
    assert items == []
