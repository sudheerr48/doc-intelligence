"""
AI provider detection and client management.

Handles lazy initialization of LLM and embedding clients,
auto-detection from environment variables, and the unified chat interface.
"""

import os
import json
from typing import Optional


DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-20250514",
    "openai": "gpt-4o",
}

DEFAULT_EMBEDDING_MODELS = {
    "voyage": "voyage-3.5",
    "openai": "text-embedding-3-small",
}

_client = None
_active_provider: Optional[str] = None
_embedding_client = None
_embedding_provider: Optional[str] = None


# ------------------------------------------------------------------
# LLM provider
# ------------------------------------------------------------------

def _detect_provider() -> str:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    raise RuntimeError(
        "No AI API key found. Set one of:\n"
        "  ANTHROPIC_API_KEY — https://console.anthropic.com/settings/keys\n"
        "  OPENAI_API_KEY    — https://platform.openai.com/api-keys"
    )


def get_provider() -> str:
    global _active_provider
    if _active_provider is None:
        _active_provider = _detect_provider()
    return _active_provider


def set_provider(provider: str) -> None:
    global _client, _active_provider
    if provider not in ("anthropic", "openai"):
        raise ValueError(
            f"Unknown provider '{provider}'. Use 'anthropic' or 'openai'."
        )
    _active_provider = provider
    _client = None


def _get_client():
    global _client, _active_provider
    if _client is not None:
        return _client

    provider = get_provider()

    if provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY environment variable is not set.\n"
                "Get your key at https://console.anthropic.com/settings/keys"
            )
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "anthropic package not installed.\n"
                "Install with: pip install 'doc-intelligence[ai]'"
            )
        _client = anthropic.Anthropic(api_key=api_key)

    elif provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY environment variable is not set.\n"
                "Get your key at https://platform.openai.com/api-keys"
            )
        try:
            import openai
        except ImportError:
            raise ImportError(
                "openai package not installed.\n"
                "Install with: pip install 'doc-intelligence[openai]'"
            )
        _client = openai.OpenAI(api_key=api_key)

    return _client


def default_model(model: Optional[str] = None) -> str:
    if model is not None:
        return model
    return DEFAULT_MODELS[get_provider()]


def is_ai_available() -> bool:
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            import anthropic  # noqa: F401
            return True
        except ImportError:
            pass
    if os.environ.get("OPENAI_API_KEY"):
        try:
            import openai  # noqa: F401
            return True
        except ImportError:
            pass
    return False


# ------------------------------------------------------------------
# Chat interfaces
# ------------------------------------------------------------------

def chat(system: str, user_msg: str, model: str, max_tokens: int) -> str:
    """Unified chat interface for both Anthropic and OpenAI."""
    client = _get_client()
    provider = get_provider()

    if provider == "anthropic":
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
        )
        return response.content[0].text.strip()
    else:
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
        )
        return response.choices[0].message.content.strip()


def chat_with_tool(
    system: str,
    user_msg: str,
    model: str,
    max_tokens: int,
    tool_name: str,
    tool_description: str,
    tool_schema: dict,
) -> dict:
    """Call the LLM with a forced tool/function call for structured output."""
    client = _get_client()
    provider = get_provider()

    if provider == "anthropic":
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            tools=[{
                "name": tool_name,
                "description": tool_description,
                "input_schema": tool_schema,
            }],
            tool_choice={"type": "tool", "name": tool_name},
            messages=[{"role": "user", "content": user_msg}],
        )
        for block in response.content:
            if block.type == "tool_use":
                return block.input
        raise RuntimeError("Model did not return a tool_use block")
    else:
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            tools=[{
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": tool_description,
                    "parameters": tool_schema,
                },
            }],
            tool_choice={
                "type": "function",
                "function": {"name": tool_name},
            },
        )
        tool_call = response.choices[0].message.tool_calls[0]
        return json.loads(tool_call.function.arguments)


# ------------------------------------------------------------------
# Embedding provider
# ------------------------------------------------------------------

def _detect_embedding_provider() -> str:
    if os.environ.get("VOYAGE_API_KEY"):
        try:
            import voyageai  # noqa: F401
            return "voyage"
        except ImportError:
            pass
    if os.environ.get("OPENAI_API_KEY"):
        try:
            import openai  # noqa: F401
            return "openai"
        except ImportError:
            pass
    raise RuntimeError(
        "No embedding API key found. Set one of:\n"
        "  VOYAGE_API_KEY  — Voyage AI (Anthropic partner): pip install voyageai\n"
        "  OPENAI_API_KEY  — OpenAI embeddings: pip install openai"
    )


def get_embedding_client():
    global _embedding_client, _embedding_provider
    if _embedding_client is not None:
        return _embedding_client

    _embedding_provider = _detect_embedding_provider()

    if _embedding_provider == "voyage":
        api_key = os.environ.get("VOYAGE_API_KEY", "")
        try:
            import voyageai
        except ImportError:
            raise ImportError(
                "voyageai package not installed.\n"
                "Install with: pip install voyageai"
            )
        _embedding_client = voyageai.Client(api_key=api_key)

    elif _embedding_provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set.")
        try:
            import openai
        except ImportError:
            raise ImportError(
                "openai package not installed.\n"
                "Install with: pip install 'doc-intelligence[openai]'"
            )
        _embedding_client = openai.OpenAI(api_key=api_key)

    return _embedding_client


def get_embedding_provider() -> str:
    global _embedding_provider
    if _embedding_provider is None:
        _embedding_provider = _detect_embedding_provider()
    return _embedding_provider


def is_embedding_available() -> bool:
    if os.environ.get("VOYAGE_API_KEY"):
        try:
            import voyageai  # noqa: F401
            return True
        except ImportError:
            pass
    if os.environ.get("OPENAI_API_KEY"):
        try:
            import openai  # noqa: F401
            return True
        except ImportError:
            pass
    return False
