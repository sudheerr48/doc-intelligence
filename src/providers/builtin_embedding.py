"""
Built-in embedding provider — wraps Voyage AI and OpenAI embedding APIs.
"""

from __future__ import annotations

from typing import Optional

from src.ai.embeddings import generate_embeddings
from src.ai.providers import is_embedding_available


class BuiltinEmbedding:
    """Default embedding provider using Voyage AI or OpenAI (auto-detected from API keys)."""

    def __init__(self, model: Optional[str] = None, batch_size: int = 100):
        self._model = model
        self._batch_size = batch_size

    def embed(self, texts: list[str], model: Optional[str] = None) -> list[list[float]]:
        return generate_embeddings(
            texts,
            model=model or self._model,
            batch_size=self._batch_size,
        )

    def is_available(self) -> bool:
        return is_embedding_available()
