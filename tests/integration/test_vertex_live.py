import asyncio
import os

import pytest
from lotus_api.agents.orchestrator import OrchestrationService
from lotus_api.config import Settings
from lotus_api.embeddings import AgentPlatformEmbedder, DeterministicEmbedder
from lotus_api.models import AgentName, AuthContext, ChatRequest
from lotus_api.storage.memory import MemoryKnowledgeStore


@pytest.mark.skipif(
    not os.getenv("GOOGLE_CLOUD_PROJECT"),
    reason="GOOGLE_CLOUD_PROJECT and ADC are required for live Agent Platform embeddings",
)
def test_live_multilingual_embedding_dimensions() -> None:
    embedder = AgentPlatformEmbedder(
        Settings(runtime_mode="agent_platform", embedding_runtime_mode="agent_platform")
    )
    vectors = embedder.embed_documents(["checkout retry policy", "चेकआउट पुनः प्रयास नीति"])
    assert len(vectors) == 2
    assert all(len(vector) == 768 for vector in vectors)


@pytest.mark.skipif(
    not os.getenv("GOOGLE_CLOUD_PROJECT"),
    reason="GOOGLE_CLOUD_PROJECT and ADC are required for live Google Search grounding",
)
def test_live_web_plan_and_grounding_have_public_citations() -> None:
    settings = Settings(
        runtime_mode="agent_platform",
        embedding_runtime_mode="fixture",
        store_backend="memory",
    )
    service = OrchestrationService(
        settings, MemoryKnowledgeStore(settings, DeterministicEmbedder())
    )
    request = ChatRequest(
        message="Research the current public Google ADK observability guidance on the web",
        project_id="payments",
    )
    plan = asyncio.run(service._plan_with_adk(request))
    assert [step.agent for step in plan.steps] == [AgentName.WEB, AgentName.RESULT]
    evidence = asyncio.run(
        service._live_web(
            request,
            AuthContext(tenant_id="demo", user_id="live-test", principals=("group:demo",)),
        )
    )
    assert evidence
    assert all(row.source_system == "web" for row in evidence)
    assert all(row.uri and row.title for row in evidence)
