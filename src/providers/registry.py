"""
Plugin registry — maps component types and names to implementations.

Usage:
    from src.providers.registry import register, get_provider, list_providers

    # Register a new provider
    register("extractor", "unstructured", UnstructuredExtractor)

    # Get a registered provider class
    cls = get_provider("extractor", "unstructured")

    # List all providers for a component type
    names = list_providers("extractor")  # ["builtin", "unstructured"]
"""

from __future__ import annotations

from typing import Any

# Component type -> {name -> class}
_registry: dict[str, dict[str, type]] = {
    "extractor": {},
    "embedding": {},
    "llm": {},
    "classifier": {},
    "vectorstore": {},
}

# Valid component types
COMPONENT_TYPES = frozenset(_registry.keys())


def register(component_type: str, name: str, cls: type) -> None:
    """Register a provider implementation.

    Args:
        component_type: One of 'extractor', 'embedding', 'llm', 'classifier', 'vectorstore'
        name: Short name for this implementation (e.g. 'builtin', 'openai', 'unstructured')
        cls: The class to register. Must conform to the relevant Protocol.
    """
    if component_type not in COMPONENT_TYPES:
        raise ValueError(
            f"Unknown component type '{component_type}'. "
            f"Must be one of: {', '.join(sorted(COMPONENT_TYPES))}"
        )
    _registry[component_type][name] = cls


def get_provider(component_type: str, name: str) -> type:
    """Get a registered provider class by type and name.

    Raises KeyError with a helpful message if not found.
    """
    if component_type not in COMPONENT_TYPES:
        raise ValueError(
            f"Unknown component type '{component_type}'. "
            f"Must be one of: {', '.join(sorted(COMPONENT_TYPES))}"
        )
    providers = _registry[component_type]
    if name not in providers:
        available = ", ".join(sorted(providers.keys())) or "(none registered)"
        raise KeyError(
            f"No '{name}' provider registered for '{component_type}'. "
            f"Available: {available}"
        )
    return providers[name]


def list_providers(component_type: str) -> list[str]:
    """List all registered provider names for a component type."""
    if component_type not in COMPONENT_TYPES:
        raise ValueError(
            f"Unknown component type '{component_type}'. "
            f"Must be one of: {', '.join(sorted(COMPONENT_TYPES))}"
        )
    return sorted(_registry[component_type].keys())


def list_all() -> dict[str, list[str]]:
    """List all registered providers, keyed by component type."""
    return {ct: sorted(providers.keys()) for ct, providers in _registry.items()}
