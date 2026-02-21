"""
AI Module
Provides AI-powered file classification, natural language queries,
and intelligent health insights using the Anthropic Claude API.

Requires: pip install 'doc-intelligence[ai]'
Set ANTHROPIC_API_KEY environment variable before use.
"""

import os
import json
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Lazy Anthropic client
# ---------------------------------------------------------------------------

_client = None


def _get_client():
    """Get or create the Anthropic client (lazy init)."""
    global _client
    if _client is not None:
        return _client

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
    return _client


# ---------------------------------------------------------------------------
# File classification / tagging
# ---------------------------------------------------------------------------

CLASSIFY_SYSTEM = """\
You are a file classification assistant. Given file metadata (name, extension, \
path, size, and optionally a content snippet), assign 2-5 descriptive tags.

Rules:
- Tags must be lowercase, hyphenated (e.g. "tax-return", "source-code", "meeting-notes")
- Be specific: prefer "python-script" over "code", "invoice-pdf" over "document"
- Include one broad category tag (e.g. "finance", "development", "media", "personal")
- Include a content-type tag (e.g. "spreadsheet", "image", "video", "pdf-document")
- If content text is provided, use it to infer purpose/topic
- Return ONLY a JSON array of strings. No explanation.
"""


def classify_file(
    name: str,
    extension: str,
    path: str,
    size_bytes: int,
    content_text: Optional[str] = None,
    model: str = "claude-sonnet-4-20250514",
) -> list[str]:
    """
    Classify a single file and return tags.

    Args:
        name: File name
        extension: File extension (e.g. ".pdf")
        path: Full file path
        size_bytes: File size in bytes
        content_text: Optional extracted text content
        model: Claude model to use

    Returns:
        List of tag strings
    """
    client = _get_client()

    snippet = ""
    if content_text:
        snippet = f"\nContent preview (first 500 chars):\n{content_text[:500]}"

    user_msg = (
        f"File: {name}\n"
        f"Extension: {extension}\n"
        f"Path: {path}\n"
        f"Size: {size_bytes} bytes"
        f"{snippet}"
    )

    response = client.messages.create(
        model=model,
        max_tokens=200,
        system=CLASSIFY_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )

    text = response.content[0].text.strip()
    return _parse_tags(text)


def classify_batch(
    files: list[dict],
    model: str = "claude-sonnet-4-20250514",
    batch_size: int = 20,
) -> dict[str, list[str]]:
    """
    Classify multiple files in batches. Each batch is sent as a single
    prompt with multiple files to reduce API calls.

    Args:
        files: List of dicts with keys: path, name, extension, size_bytes, content_text
        model: Claude model to use
        batch_size: Files per API call

    Returns:
        Dict mapping path -> list of tags
    """
    client = _get_client()
    results: dict[str, list[str]] = {}

    for i in range(0, len(files), batch_size):
        batch = files[i : i + batch_size]
        file_descriptions = []

        for idx, f in enumerate(batch, 1):
            snippet = ""
            if f.get("content_text"):
                snippet = f"\n  Content: {f['content_text'][:200]}"
            file_descriptions.append(
                f"[{idx}] {f['name']} | ext={f['extension']} | "
                f"size={f['size_bytes']}b | path={f['path']}{snippet}"
            )

        user_msg = (
            "Classify each file below with 2-5 tags. "
            "Return a JSON object mapping the file number (as string) to an array of tags.\n"
            "Example: {\"1\": [\"python-script\", \"development\"], \"2\": [\"photo\", \"media\"]}\n\n"
            + "\n".join(file_descriptions)
        )

        response = client.messages.create(
            model=model,
            max_tokens=1500,
            system=CLASSIFY_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )

        text = response.content[0].text.strip()
        batch_tags = _parse_batch_tags(text)

        for idx_str, tags in batch_tags.items():
            try:
                idx = int(idx_str) - 1
                if 0 <= idx < len(batch):
                    results[batch[idx]["path"]] = tags
            except (ValueError, IndexError):
                continue

    return results


# ---------------------------------------------------------------------------
# Natural language query
# ---------------------------------------------------------------------------

NL_QUERY_SYSTEM = """\
You are a SQL query generator for a DuckDB database. The database has a single \
table called `files` with this schema:

CREATE TABLE files (
    path VARCHAR PRIMARY KEY,
    name VARCHAR,
    extension VARCHAR,
    size_bytes BIGINT,
    created_at TIMESTAMP,
    modified_at TIMESTAMP,
    content_hash VARCHAR,
    category VARCHAR,
    scanned_at TIMESTAMP,
    content_text VARCHAR,
    tags VARCHAR  -- JSON array of strings, e.g. '["finance", "invoice-pdf"]'
);

Rules:
- Generate ONLY a valid DuckDB SELECT query. No explanation, no markdown fences.
- Use ILIKE for case-insensitive text matching.
- For tag queries, use: tags LIKE '%"tag-name"%'
- For size queries: 1 KB = 1024, 1 MB = 1048576, 1 GB = 1073741824
- Always add LIMIT 100 unless the user specifies a different limit.
- For aggregation queries (count, sum, avg), still limit grouping results.
- Common patterns:
  - "PDFs over 10MB" → extension = '.pdf' AND size_bytes > 10485760
  - "duplicate files" → GROUP BY content_hash HAVING COUNT(*) > 1
  - "largest files" → ORDER BY size_bytes DESC
  - "recently modified" → ORDER BY modified_at DESC
  - "files tagged as X" → tags LIKE '%"X"%'
"""


def nl_to_sql(query: str, model: str = "claude-sonnet-4-20250514") -> str:
    """
    Convert a natural language query to a DuckDB SQL SELECT statement.

    Args:
        query: Natural language question about the file index
        model: Claude model to use

    Returns:
        SQL SELECT query string
    """
    client = _get_client()

    response = client.messages.create(
        model=model,
        max_tokens=500,
        system=NL_QUERY_SYSTEM,
        messages=[{"role": "user", "content": query}],
    )

    sql = response.content[0].text.strip()

    # Strip markdown code fences if model included them
    if sql.startswith("```"):
        lines = sql.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        sql = "\n".join(lines).strip()

    return sql


# ---------------------------------------------------------------------------
# Health insights (AI-enhanced)
# ---------------------------------------------------------------------------

HEALTH_SYSTEM = """\
You are a file system health analyst. Given metrics about a user's indexed files, \
provide a concise health report with actionable recommendations.

Format your response as a JSON object with these keys:
- "score": integer 0-100 (100 = perfectly healthy)
- "grade": string ("A", "B", "C", "D", "F")
- "summary": string (2-3 sentence overview)
- "issues": array of {"severity": "high"|"medium"|"low", "title": string, "detail": string}
- "recommendations": array of strings (3-5 actionable suggestions)

Be specific with numbers. Reference actual file names and sizes when relevant.\
"""


def generate_health_insights(metrics: dict, model: str = "claude-sonnet-4-20250514") -> dict:
    """
    Generate AI-powered health insights from file system metrics.

    Args:
        metrics: Health metrics dict from FileDatabase.get_health_metrics()
        model: Claude model to use

    Returns:
        Dict with score, grade, summary, issues, recommendations
    """
    client = _get_client()

    # Build a compact metrics summary for the prompt
    metrics_text = json.dumps(metrics, indent=2, default=str)

    response = client.messages.create(
        model=model,
        max_tokens=1000,
        system=HEALTH_SYSTEM,
        messages=[{"role": "user", "content": f"Analyze these file system metrics:\n\n{metrics_text}"}],
    )

    text = response.content[0].text.strip()

    # Strip markdown fences
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "score": 0,
            "grade": "?",
            "summary": "Could not parse AI response.",
            "issues": [],
            "recommendations": [text],
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_tags(text: str) -> list[str]:
    """Parse a JSON array of tags from model output."""
    try:
        tags = json.loads(text)
        if isinstance(tags, list):
            return [str(t).lower().strip() for t in tags if t]
    except json.JSONDecodeError:
        pass

    # Fallback: extract anything that looks like tags
    tags = []
    for part in text.replace("[", "").replace("]", "").replace('"', "").split(","):
        tag = part.strip().lower()
        if tag and len(tag) < 50:
            tags.append(tag)
    return tags[:5]


def _parse_batch_tags(text: str) -> dict[str, list[str]]:
    """Parse a JSON object mapping file numbers to tag arrays."""
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return {
                str(k): [str(t).lower().strip() for t in v]
                for k, v in result.items()
                if isinstance(v, list)
            }
    except json.JSONDecodeError:
        pass
    return {}


def is_ai_available() -> bool:
    """Check if AI features are available (API key set and package installed)."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        return False
