"""
AI package — LLM-powered classification, embeddings, queries, and health insights.

Supported providers:
  - Anthropic Claude: pip install 'doc-intelligence[ai]' + ANTHROPIC_API_KEY
  - OpenAI: pip install 'doc-intelligence[openai]' + OPENAI_API_KEY

Embedding providers:
  - Voyage AI: VOYAGE_API_KEY (voyage-3.5) — Anthropic's embedding partner
  - OpenAI: OPENAI_API_KEY (text-embedding-3-small)
"""

from .providers import (
    get_provider,
    set_provider,
    is_ai_available,
    is_embedding_available,
    DEFAULT_MODELS,
    DEFAULT_EMBEDDING_MODELS,
)
from .classification import classify_file, classify_batch
from .embeddings import generate_embeddings
from .query import nl_to_sql
from .insights import generate_health_insights

__all__ = [
    "get_provider",
    "set_provider",
    "is_ai_available",
    "is_embedding_available",
    "DEFAULT_MODELS",
    "DEFAULT_EMBEDDING_MODELS",
    "classify_file",
    "classify_batch",
    "generate_embeddings",
    "nl_to_sql",
    "generate_health_insights",
]
