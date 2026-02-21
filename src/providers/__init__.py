"""
Provider plugin system — swap any component via config.

Interfaces define what each component must do.
Registry maps names to implementations.
Factory creates instances from config.

To add a new provider:
    1. Implement the relevant Protocol (see interfaces.py)
    2. Register it in registry.py or via register()
    3. Set the provider name in config.yaml
"""

from .interfaces import (
    TextExtractor,
    EmbeddingProvider,
    LLMProvider,
    FileClassifier,
    VectorStore,
)
from .registry import register, get_provider, list_providers
from .factory import create_providers, Providers

# Auto-register built-in providers
from . import defaults as _defaults  # noqa: F401

__all__ = [
    # Interfaces
    "TextExtractor",
    "EmbeddingProvider",
    "LLMProvider",
    "FileClassifier",
    "VectorStore",
    # Registry
    "register",
    "get_provider",
    "list_providers",
    # Factory
    "create_providers",
    "Providers",
]
