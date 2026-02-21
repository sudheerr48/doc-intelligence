"""
Protocol interfaces for all swappable components.

Each Protocol defines the contract a provider must satisfy.
Implementations don't need to inherit — they just need matching methods
(structural subtyping via typing.Protocol).
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class TextExtractor(Protocol):
    """Extract text content from files."""

    def extract(self, file_path: str) -> Optional[str]:
        """Extract text from a file. Return None if unsupported or failed."""
        ...

    def supported_extensions(self) -> set[str]:
        """Return the set of file extensions this extractor handles."""
        ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Generate vector embeddings from text."""

    def embed(self, texts: list[str], model: Optional[str] = None) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        ...

    def is_available(self) -> bool:
        """Check if this provider is configured and ready."""
        ...


@runtime_checkable
class LLMProvider(Protocol):
    """Chat with a large language model."""

    def chat(self, system: str, user_msg: str, model: Optional[str] = None,
             max_tokens: int = 1000) -> str:
        """Send a message and get a text response."""
        ...

    def chat_structured(self, system: str, user_msg: str,
                        tool_name: str, tool_schema: dict,
                        model: Optional[str] = None,
                        max_tokens: int = 1000) -> dict:
        """Send a message and get a structured (JSON) response via tool use."""
        ...

    def is_available(self) -> bool:
        """Check if this provider is configured and ready."""
        ...


@runtime_checkable
class FileClassifier(Protocol):
    """Classify files and assign tags."""

    def classify(self, files: list[dict],
                 batch_size: int = 20) -> dict[str, list[str]]:
        """Classify files and return {path: [tags]} mapping."""
        ...


@runtime_checkable
class VectorStore(Protocol):
    """Store and search vector embeddings."""

    def store(self, items: list[tuple[str, list[float]]], model: str) -> int:
        """Store embeddings. Returns count stored."""
        ...

    def search(self, query_embedding: list[float],
               limit: int = 20) -> list[dict]:
        """Find similar items. Returns list of dicts with 'path', 'similarity', etc."""
        ...

    def stats(self) -> dict:
        """Return embedding statistics."""
        ...
