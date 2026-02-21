"""
Built-in text extractor — wraps the existing extraction logic.

Handles PDF (pypdf), DOCX (python-docx), XLSX (openpyxl), and plaintext.
"""

from __future__ import annotations

from typing import Optional

from src.scanner.extractors import extract_text, _PLAINTEXT_EXTS, MAX_TEXT_LENGTH


class BuiltinExtractor:
    """Default text extractor using pypdf, python-docx, openpyxl."""

    def __init__(self, max_length: int = MAX_TEXT_LENGTH):
        self.max_length = max_length

    def extract(self, file_path: str) -> Optional[str]:
        return extract_text(file_path)

    def supported_extensions(self) -> set[str]:
        return set(_PLAINTEXT_EXTS) | {".pdf", ".docx", ".xlsx"}
