"""
Built-in LLM provider — wraps the existing Anthropic/OpenAI logic.

Auto-detects provider from API keys, supports both Anthropic and OpenAI.
"""

from __future__ import annotations

from typing import Optional

from src.ai.providers import (
    chat,
    chat_with_tool,
    default_model,
    is_ai_available,
    get_provider,
    set_provider,
)


class BuiltinLLM:
    """Default LLM using Anthropic Claude or OpenAI GPT (auto-detected from API keys)."""

    def __init__(self, provider: Optional[str] = None):
        if provider and provider != "auto":
            set_provider(provider)

    def chat(self, system: str, user_msg: str, model: Optional[str] = None,
             max_tokens: int = 1000) -> str:
        return chat(system, user_msg, default_model(model), max_tokens)

    def chat_structured(self, system: str, user_msg: str,
                        tool_name: str, tool_schema: dict,
                        model: Optional[str] = None,
                        max_tokens: int = 1000) -> dict:
        return chat_with_tool(
            system=system,
            user_msg=user_msg,
            model=default_model(model),
            max_tokens=max_tokens,
            tool_name=tool_name,
            tool_description=tool_name,
            tool_schema=tool_schema,
        )

    def is_available(self) -> bool:
        return is_ai_available()
