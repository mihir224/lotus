import hashlib
import math
import re
from collections.abc import Sequence
from typing import Protocol

from google import genai
from google.genai.types import EmbedContentConfig

from .config import Settings

TOKEN = re.compile(r"\w+", re.UNICODE)


class Embedder(Protocol):
    model_id: str
    dimensions: int

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class DeterministicEmbedder:
    """Dependency-free embeddings for repeatable fixture and test retrieval."""

    def __init__(self, dimensions: int = 768):
        self.dimensions = dimensions
        self.model_id = f"fixture:hash-v1:{dimensions}"

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        normalized = text.casefold()
        features = TOKEN.findall(normalized)
        features.extend(
            normalized[index : index + 3] for index in range(max(0, len(normalized) - 2))
        )
        for feature in features:
            digest = hashlib.sha256(feature.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class VertexEmbedder:
    def __init__(self, settings: Settings):
        self.client = genai.Client(
            vertexai=True,
            project=settings.google_cloud_project,
            location=settings.google_cloud_location,
        )
        self.model = settings.embedding_model
        self.dimensions = settings.embedding_dimensions
        self.model_id = f"vertex:{self.model}:{self.dimensions}"

    def _embed(self, texts: Sequence[str], task_type: str) -> list[list[float]]:
        response = self.client.models.embed_content(
            model=self.model,
            contents=list(texts),
            config=EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=self.dimensions,
            ),
        )
        return [list(item.values or []) for item in response.embeddings or []]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._embed(texts, "RETRIEVAL_DOCUMENT")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], "RETRIEVAL_QUERY")[0]


def build_embedder(settings: Settings) -> Embedder:
    if settings.runtime_mode == "vertex":
        return VertexEmbedder(settings)
    return DeterministicEmbedder(settings.embedding_dimensions)
