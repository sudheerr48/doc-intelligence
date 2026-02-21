"""
Register all built-in providers.

This module is imported by the providers package __init__.py to ensure
the default implementations are always available in the registry.
"""

from .registry import register
from .builtin_extractor import BuiltinExtractor
from .builtin_embedding import BuiltinEmbedding
from .builtin_llm import BuiltinLLM
from .builtin_classifier import BuiltinClassifier
from .builtin_vectorstore import BuiltinVectorStore

register("extractor", "builtin", BuiltinExtractor)
register("embedding", "builtin", BuiltinEmbedding)
register("llm", "builtin", BuiltinLLM)
register("classifier", "builtin", BuiltinClassifier)
register("vectorstore", "builtin", BuiltinVectorStore)
