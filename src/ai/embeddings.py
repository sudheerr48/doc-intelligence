"""
Embedding generation — Voyage AI and OpenAI providers.
"""

from typing import Optional

from .providers import (
    get_embedding_client,
    get_embedding_provider,
    DEFAULT_EMBEDDING_MODELS,
)


def generate_embeddings(
    texts: list[str],
    model: Optional[str] = None,
    batch_size: int = 100,
) -> list[list[float]]:
    """
    Generate embeddings for a list of texts.
    Auto-selects between Voyage AI and OpenAI based on available API keys.
    """
    client = get_embedding_client()
    provider = get_embedding_provider()

    if model is None:
        model = DEFAULT_EMBEDDING_MODELS.get(provider, "text-embedding-3-small")

    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        batch = [t[:8000] if len(t) > 8000 else t for t in batch]

        if provider == "voyage":
            result = client.embed(batch, model=model, input_type="document")
            all_embeddings.extend(result.embeddings)
        else:
            response = client.embeddings.create(model=model, input=batch)
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)

    return all_embeddings
