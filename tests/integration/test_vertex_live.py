import os

import pytest
from lotus_api.config import Settings
from lotus_api.embeddings import VertexEmbedder


@pytest.mark.skipif(
    not os.getenv("GOOGLE_CLOUD_PROJECT"),
    reason="GOOGLE_CLOUD_PROJECT and Vertex credentials are required for live embeddings",
)
def test_live_multilingual_embedding_dimensions() -> None:
    embedder = VertexEmbedder(Settings(runtime_mode="vertex"))
    vectors = embedder.embed_documents(
        ["checkout retry policy", "चेकआउट पुनः प्रयास नीति"]
    )
    assert len(vectors) == 2
    assert all(len(vector) == 768 for vector in vectors)
