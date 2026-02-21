"""Backward-compatible re-exports — use src.ai.* submodules instead."""
from src.ai.providers import (  # noqa: F401
    get_provider,
    set_provider,
    is_ai_available,
    is_embedding_available,
    DEFAULT_MODELS,
    DEFAULT_EMBEDDING_MODELS,
    _detect_provider,
    _detect_embedding_provider,
    _get_client,
    get_embedding_client,
    get_embedding_provider,
    chat,
    chat_with_tool,
    default_model,
)
from src.ai.classification import (  # noqa: F401
    classify_file,
    classify_batch,
    _parse_tags,
    _parse_batch_tags,
)
from src.ai.embeddings import generate_embeddings  # noqa: F401
from src.ai.query import nl_to_sql  # noqa: F401
from src.ai.insights import generate_health_insights  # noqa: F401
