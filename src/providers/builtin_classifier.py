"""
Built-in file classifier — wraps the existing LLM-based classification.
"""

from __future__ import annotations

from src.ai.classification import classify_batch


class BuiltinClassifier:
    """Default classifier using LLM-based tagging (Anthropic or OpenAI)."""

    def __init__(self, model: str | None = None):
        self._model = model

    def classify(self, files: list[dict],
                 batch_size: int = 20) -> dict[str, list[str]]:
        return classify_batch(files, model=self._model, batch_size=batch_size)
