"""
Text Extraction Module
Extracts text content from files for full-text search.
Supports PDF and plain text files.
"""

from pathlib import Path
from typing import Optional

# Maximum text to store per file (64KB)
MAX_TEXT_LENGTH = 65536


def extract_text(file_path: str) -> Optional[str]:
    """
    Extract text content from a file based on its extension.

    Args:
        file_path: Path to the file

    Returns:
        Extracted text, or None if extraction fails or is unsupported
    """
    ext = Path(file_path).suffix.lower()

    try:
        if ext == ".pdf":
            return _extract_pdf(file_path)
        elif ext in (".txt", ".csv", ".md", ".json", ".xml", ".html", ".htm",
                      ".log", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
                      ".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".go",
                      ".rs", ".rb", ".sh", ".bat", ".sql"):
            return _extract_plaintext(file_path)
        else:
            return None
    except Exception:
        return None


def _extract_pdf(file_path: str) -> Optional[str]:
    """Extract text from a PDF file using pypdf."""
    try:
        from pypdf import PdfReader

        reader = PdfReader(file_path)
        pages = []
        total_len = 0

        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
                total_len += len(text)
                if total_len >= MAX_TEXT_LENGTH:
                    break

        if not pages:
            return None

        full_text = "\n".join(pages)
        if len(full_text) > MAX_TEXT_LENGTH:
            full_text = full_text[:MAX_TEXT_LENGTH]

        return full_text.strip() or None
    except BaseException:
        # BaseException catches import failures (e.g. missing cffi)
        # and Rust panics from cryptography bindings
        return None


def _extract_plaintext(file_path: str) -> Optional[str]:
    """Extract text from a plain text file."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read(MAX_TEXT_LENGTH)
        return text.strip() or None
    except Exception:
        return None
