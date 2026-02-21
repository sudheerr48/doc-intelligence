"""
AI Module
Provides AI-powered file classification, natural language queries,
and intelligent health insights using LLM APIs.

Supported providers:
  - Anthropic Claude: pip install 'doc-intelligence[ai]' + ANTHROPIC_API_KEY
  - OpenAI: pip install 'doc-intelligence[openai]' + OPENAI_API_KEY

Embedding providers:
  - OpenAI: OPENAI_API_KEY (text-embedding-3-small)
  - Voyage AI: VOYAGE_API_KEY (voyage-3.5) — Anthropic's embedding partner

Uses structured outputs (tool_use / function calling) instead of fragile
prompt-and-parse for reliable JSON responses.
"""

import os
import json
from typing import Optional


# ---------------------------------------------------------------------------
# Provider detection and client management
# ---------------------------------------------------------------------------

DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-20250514",
    "openai": "gpt-4o",
}

_client = None
_active_provider: Optional[str] = None


def _detect_provider() -> str:
    """Auto-detect which AI provider to use based on available API keys."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    raise RuntimeError(
        "No AI API key found. Set one of:\n"
        "  ANTHROPIC_API_KEY — get yours at https://console.anthropic.com/settings/keys\n"
        "  OPENAI_API_KEY    — get yours at https://platform.openai.com/api-keys"
    )


def get_provider() -> str:
    """Return the currently active provider name."""
    global _active_provider
    if _active_provider is None:
        _active_provider = _detect_provider()
    return _active_provider


def set_provider(provider: str) -> None:
    """Explicitly set the AI provider ('anthropic' or 'openai')."""
    global _client, _active_provider
    if provider not in ("anthropic", "openai"):
        raise ValueError(f"Unknown provider '{provider}'. Use 'anthropic' or 'openai'.")
    _active_provider = provider
    _client = None  # reset cached client


def _get_client():
    """Get or create the LLM client (lazy init)."""
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


def _chat(system: str, user_msg: str, model: str, max_tokens: int) -> str:
    """Unified chat interface that works with both Anthropic and OpenAI."""
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

    else:  # openai
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
        )
        return response.choices[0].message.content.strip()


def _default_model(model: Optional[str] = None) -> str:
    """Return the given model or the default for the active provider."""
    if model is not None:
        return model
    return DEFAULT_MODELS[get_provider()]


# ---------------------------------------------------------------------------
# Structured output via tool_use / function calling
# ---------------------------------------------------------------------------

def _chat_with_tool(
    system: str,
    user_msg: str,
    model: str,
    max_tokens: int,
    tool_name: str,
    tool_description: str,
    tool_schema: dict,
) -> dict:
    """
    Call the LLM with a forced tool/function call to get guaranteed structured output.

    Uses Anthropic tool_use or OpenAI function calling depending on provider.
    The model is forced to respond via the tool, so the output always matches the schema.

    Args:
        system: System prompt
        user_msg: User message
        model: Model name
        max_tokens: Max tokens
        tool_name: Name of the tool
        tool_description: Description of the tool
        tool_schema: JSON Schema for the tool's input

    Returns:
        Dict matching the tool schema
    """
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
        # Find the tool_use block
        for block in response.content:
            if block.type == "tool_use":
                return block.input
        # Fallback — should not happen with forced tool_choice
        raise RuntimeError("Model did not return a tool_use block")

    else:  # openai
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
            tool_choice={"type": "function", "function": {"name": tool_name}},
        )
        tool_call = response.choices[0].message.tool_calls[0]
        return json.loads(tool_call.function.arguments)


# ---------------------------------------------------------------------------
# Tool schemas for structured outputs
# ---------------------------------------------------------------------------

_CLASSIFY_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "2-5 lowercase, hyphenated descriptive tags for the file",
        }
    },
    "required": ["tags"],
}

_CLASSIFY_BATCH_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "classifications": {
            "type": "object",
            "additionalProperties": {
                "type": "array",
                "items": {"type": "string"},
            },
            "description": "Mapping of file number (as string) to array of tags",
        }
    },
    "required": ["classifications"],
}

_SQL_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "sql": {
            "type": "string",
            "description": "A valid DuckDB SELECT query",
        }
    },
    "required": ["sql"],
}

_HEALTH_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {
            "type": "integer",
            "description": "Health score 0-100 (100 = perfectly healthy)",
        },
        "grade": {
            "type": "string",
            "description": "Letter grade: A, B, C, D, or F",
        },
        "summary": {
            "type": "string",
            "description": "2-3 sentence overview of file system health",
        },
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["high", "medium", "low"]},
                    "title": {"type": "string"},
                    "detail": {"type": "string"},
                },
                "required": ["severity", "title", "detail"],
            },
            "description": "List of issues found",
        },
        "recommendations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "3-5 actionable suggestions",
        },
    },
    "required": ["score", "grade", "summary", "issues", "recommendations"],
}


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
- If content text is provided, use it to infer purpose/topic\
"""


def classify_file(
    name: str,
    extension: str,
    path: str,
    size_bytes: int,
    content_text: Optional[str] = None,
    model: Optional[str] = None,
) -> list[str]:
    """
    Classify a single file and return tags.
    Uses structured output (tool_use) for reliable JSON responses.

    Args:
        name: File name
        extension: File extension (e.g. ".pdf")
        path: Full file path
        size_bytes: File size in bytes
        content_text: Optional extracted text content
        model: LLM model to use (defaults to provider's default)

    Returns:
        List of tag strings
    """
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

    try:
        result = _chat_with_tool(
            system=CLASSIFY_SYSTEM,
            user_msg=user_msg,
            model=_default_model(model),
            max_tokens=200,
            tool_name="classify_file",
            tool_description="Classify a file with descriptive tags",
            tool_schema=_CLASSIFY_TOOL_SCHEMA,
        )
        tags = result.get("tags", [])
        return [str(t).lower().strip() for t in tags if t][:5]
    except Exception:
        # Fallback to plain chat + parsing if tool_use fails
        text = _chat(
            CLASSIFY_SYSTEM + "\nReturn ONLY a JSON array of strings. No explanation.",
            user_msg, _default_model(model), max_tokens=200,
        )
        return _parse_tags(text)


def classify_batch(
    files: list[dict],
    model: Optional[str] = None,
    batch_size: int = 20,
) -> dict[str, list[str]]:
    """
    Classify multiple files in batches using structured output.

    Args:
        files: List of dicts with keys: path, name, extension, size_bytes, content_text
        model: LLM model to use (defaults to provider's default)
        batch_size: Files per API call

    Returns:
        Dict mapping path -> list of tags
    """
    resolved_model = _default_model(model)
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
            "Classify each file below with 2-5 tags.\n\n"
            + "\n".join(file_descriptions)
        )

        try:
            result = _chat_with_tool(
                system=CLASSIFY_SYSTEM,
                user_msg=user_msg,
                model=resolved_model,
                max_tokens=1500,
                tool_name="classify_batch",
                tool_description="Classify multiple files with descriptive tags",
                tool_schema=_CLASSIFY_BATCH_TOOL_SCHEMA,
            )
            batch_tags = result.get("classifications", {})
        except Exception:
            # Fallback to plain chat + parsing
            user_msg_fallback = (
                "Classify each file below with 2-5 tags. "
                "Return a JSON object mapping the file number (as string) to an array of tags.\n"
                'Example: {"1": ["python-script", "development"], "2": ["photo", "media"]}\n\n'
                + "\n".join(file_descriptions)
            )
            text = _chat(
                CLASSIFY_SYSTEM + "\nReturn ONLY a JSON object. No explanation.",
                user_msg_fallback, resolved_model, max_tokens=1500,
            )
            batch_tags = _parse_batch_tags(text)

        for idx_str, tags in batch_tags.items():
            try:
                idx = int(idx_str) - 1
                if 0 <= idx < len(batch):
                    results[batch[idx]["path"]] = [
                        str(t).lower().strip() for t in tags if t
                    ]
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
- Generate a valid DuckDB SELECT query.
- Use ILIKE for case-insensitive text matching.
- For tag queries, use: tags LIKE '%"tag-name"%'
- For size queries: 1 KB = 1024, 1 MB = 1048576, 1 GB = 1073741824
- Always add LIMIT 100 unless the user specifies a different limit.
- For aggregation queries (count, sum, avg), still limit grouping results.
- Common patterns:
  - "PDFs over 10MB" -> extension = '.pdf' AND size_bytes > 10485760
  - "duplicate files" -> GROUP BY content_hash HAVING COUNT(*) > 1
  - "largest files" -> ORDER BY size_bytes DESC
  - "recently modified" -> ORDER BY modified_at DESC
  - "files tagged as X" -> tags LIKE '%"X"%'\
"""


def nl_to_sql(query: str, model: Optional[str] = None) -> str:
    """
    Convert a natural language query to a DuckDB SQL SELECT statement.
    Uses structured output (tool_use) to guarantee clean SQL without markdown fences.

    Args:
        query: Natural language question about the file index
        model: LLM model to use (defaults to provider's default)

    Returns:
        SQL SELECT query string
    """
    try:
        result = _chat_with_tool(
            system=NL_QUERY_SYSTEM,
            user_msg=query,
            model=_default_model(model),
            max_tokens=500,
            tool_name="generate_sql",
            tool_description="Generate a DuckDB SELECT query from natural language",
            tool_schema=_SQL_TOOL_SCHEMA,
        )
        return result["sql"]
    except Exception:
        # Fallback to plain chat + fence stripping
        sql = _chat(
            NL_QUERY_SYSTEM + "\nReturn ONLY the SQL query. No explanation, no markdown fences.",
            query, _default_model(model), max_tokens=500,
        )
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

Be specific with numbers. Reference actual file names and sizes when relevant.\
"""


def generate_health_insights(metrics: dict, model: Optional[str] = None) -> dict:
    """
    Generate AI-powered health insights from file system metrics.
    Uses structured output (tool_use) for reliable JSON responses.

    Args:
        metrics: Health metrics dict from FileDatabase.get_health_metrics()
        model: LLM model to use (defaults to provider's default)

    Returns:
        Dict with score, grade, summary, issues, recommendations
    """
    metrics_text = json.dumps(metrics, indent=2, default=str)

    try:
        return _chat_with_tool(
            system=HEALTH_SYSTEM,
            user_msg=f"Analyze these file system metrics:\n\n{metrics_text}",
            model=_default_model(model),
            max_tokens=1000,
            tool_name="health_report",
            tool_description="Generate a file system health report",
            tool_schema=_HEALTH_TOOL_SCHEMA,
        )
    except Exception:
        # Fallback to plain chat + JSON parsing
        text = _chat(
            HEALTH_SYSTEM + (
                '\nFormat your response as a JSON object with keys: '
                '"score" (int 0-100), "grade" (string), "summary" (string), '
                '"issues" (array), "recommendations" (array).'
            ),
            f"Analyze these file system metrics:\n\n{metrics_text}",
            _default_model(model),
            max_tokens=1000,
        )
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
# Helpers (kept as fallbacks for plain-text mode)
# ---------------------------------------------------------------------------

def _parse_tags(text: str) -> list[str]:
    """Parse a JSON array of tags from model output (fallback for non-tool mode)."""
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
    """Parse a JSON object mapping file numbers to tag arrays (fallback)."""
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


# ---------------------------------------------------------------------------
# Embedding providers: OpenAI + Voyage AI
# ---------------------------------------------------------------------------

DEFAULT_EMBEDDING_MODELS = {
    "voyage": "voyage-3.5",
    "openai": "text-embedding-3-small",
}

_embedding_client = None
_embedding_provider: Optional[str] = None


def _detect_embedding_provider() -> str:
    """Auto-detect which embedding provider to use."""
    # Prefer Voyage AI if available (Anthropic's partner, no OpenAI dependency)
    if os.environ.get("VOYAGE_API_KEY"):
        try:
            import voyageai  # noqa: F401
            return "voyage"
        except ImportError:
            pass
    # Fall back to OpenAI
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


def _get_embedding_client():
    """Get or create the embedding client (lazy init)."""
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


def generate_embeddings(
    texts: list[str],
    model: Optional[str] = None,
    batch_size: int = 100,
) -> list[list[float]]:
    """
    Generate embeddings for a list of texts.
    Automatically selects between Voyage AI and OpenAI based on available API keys.

    Args:
        texts: List of text strings to embed
        model: Embedding model name (auto-detected if None)
        batch_size: Texts per API call

    Returns:
        List of embedding vectors (list of floats)
    """
    client = _get_embedding_client()
    provider = _embedding_provider

    if model is None:
        model = DEFAULT_EMBEDDING_MODELS.get(provider, "text-embedding-3-small")

    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        # Truncate very long texts to avoid token limits
        batch = [t[:8000] if len(t) > 8000 else t for t in batch]

        if provider == "voyage":
            result = client.embed(batch, model=model, input_type="document")
            all_embeddings.extend(result.embeddings)
        else:  # openai
            response = client.embeddings.create(model=model, input=batch)
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)

    return all_embeddings


def is_embedding_available() -> bool:
    """Check if embedding features are available (needs API key + package)."""
    # Check Voyage AI first
    if os.environ.get("VOYAGE_API_KEY"):
        try:
            import voyageai  # noqa: F401
            return True
        except ImportError:
            pass
    # Check OpenAI
    if os.environ.get("OPENAI_API_KEY"):
        try:
            import openai  # noqa: F401
            return True
        except ImportError:
            pass
    return False


def is_ai_available() -> bool:
    """Check if AI features are available (API key set and package installed)."""
    # Check Anthropic
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            import anthropic  # noqa: F401
            return True
        except ImportError:
            pass

    # Check OpenAI
    if os.environ.get("OPENAI_API_KEY"):
        try:
            import openai  # noqa: F401
            return True
        except ImportError:
            pass

    return False
