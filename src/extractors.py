"""Backward-compatible re-export — use src.scanner.extractors instead."""
from src.scanner.extractors import (  # noqa: F401
    extract_text,
    MAX_TEXT_LENGTH,
    _PLAINTEXT_EXTS,
)
