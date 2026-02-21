"""
Built-in vector store — uses DuckDB's embeddings table with cosine similarity.
"""

from __future__ import annotations

from src.core.database import FileDatabase


class BuiltinVectorStore:
    """Default vector store backed by the DuckDB embeddings table."""

    def __init__(self, db: FileDatabase):
        self._db = db

    def store(self, items: list[tuple[str, list[float]]], model: str) -> int:
        return self._db.store_embeddings_batch(items, model)

    def search(self, query_embedding: list[float],
               limit: int = 20) -> list[dict]:
        return self._db.semantic_search(query_embedding, limit=limit)

    def stats(self) -> dict:
        return self._db.get_embedding_stats()
