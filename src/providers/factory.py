"""
Provider factory — creates provider instances from config.

Reads the `providers` section of config.yaml and instantiates the right
implementation for each component type.

Usage:
    from src.providers import create_providers

    providers = create_providers(config)
    text = providers.extractor.extract("file.pdf")
    vecs = providers.embedding.embed(["hello world"])
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .registry import get_provider


@dataclass
class Providers:
    """Container holding all active provider instances."""
    extractor: Any = None
    embedding: Any = None
    llm: Any = None
    classifier: Any = None
    vectorstore: Any = None


def _get_provider_config(config: dict) -> dict:
    """Extract the providers section from config, with defaults."""
    return config.get("providers", {})


def create_providers(
    config: dict,
    db: Any = None,
    overrides: Optional[dict[str, str]] = None,
) -> Providers:
    """Create all provider instances from config.

    Args:
        config: Full config dict (from load_config)
        db: FileDatabase instance (needed for vectorstore provider)
        overrides: Optional {component_type: provider_name} to override config

    Returns:
        Providers dataclass with all active provider instances.
    """
    prov_config = _get_provider_config(config)
    overrides = overrides or {}

    providers = Providers()

    # --- Extractor ---
    ext_name = overrides.get("extractor", prov_config.get("extractor", "builtin"))
    ext_opts = prov_config.get("extractor_options", {})
    ext_cls = get_provider("extractor", ext_name)
    providers.extractor = ext_cls(**ext_opts)

    # --- Embedding ---
    emb_name = overrides.get("embedding", prov_config.get("embedding", "builtin"))
    emb_opts = prov_config.get("embedding_options", {})
    emb_cls = get_provider("embedding", emb_name)
    providers.embedding = emb_cls(**emb_opts)

    # --- LLM ---
    llm_name = overrides.get("llm", prov_config.get("llm", "builtin"))
    llm_opts = prov_config.get("llm_options", {})
    llm_cls = get_provider("llm", llm_name)
    providers.llm = llm_cls(**llm_opts)

    # --- Classifier ---
    cls_name = overrides.get("classifier", prov_config.get("classifier", "builtin"))
    cls_opts = prov_config.get("classifier_options", {})
    cls_cls = get_provider("classifier", cls_name)
    providers.classifier = cls_cls(**cls_opts)

    # --- Vector Store (requires db, created lazily if db not provided) ---
    vs_name = overrides.get("vectorstore", prov_config.get("vectorstore", "builtin"))
    vs_opts = prov_config.get("vectorstore_options", {})
    vs_cls = get_provider("vectorstore", vs_name)
    if db is not None:
        providers.vectorstore = vs_cls(db=db, **vs_opts)
    else:
        # Store config for lazy initialization — vectorstore needs a db
        providers._vectorstore_cls = vs_cls
        providers._vectorstore_opts = vs_opts

    return providers
