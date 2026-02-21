"""
AI-powered file classification and tagging.
"""

import json
from typing import Optional

from .providers import chat, chat_with_tool, default_model


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

_CLASSIFY_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "2-5 lowercase, hyphenated descriptive tags for the file"
            ),
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
            "description": (
                "Mapping of file number (as string) to array of tags"
            ),
        }
    },
    "required": ["classifications"],
}


def classify_file(
    name: str,
    extension: str,
    path: str,
    size_bytes: int,
    content_text: Optional[str] = None,
    model: Optional[str] = None,
) -> list[str]:
    """Classify a single file and return tags via structured output."""
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
        result = chat_with_tool(
            system=CLASSIFY_SYSTEM,
            user_msg=user_msg,
            model=default_model(model),
            max_tokens=200,
            tool_name="classify_file",
            tool_description="Classify a file with descriptive tags",
            tool_schema=_CLASSIFY_TOOL_SCHEMA,
        )
        tags = result.get("tags", [])
        return [str(t).lower().strip() for t in tags if t][:5]
    except Exception:
        text = chat(
            CLASSIFY_SYSTEM + "\nReturn ONLY a JSON array of strings.",
            user_msg, default_model(model), max_tokens=200,
        )
        return _parse_tags(text)


def classify_batch(
    files: list[dict],
    model: Optional[str] = None,
    batch_size: int = 20,
) -> dict[str, list[str]]:
    """Classify multiple files in batches via structured output."""
    resolved_model = default_model(model)
    results: dict[str, list[str]] = {}

    for i in range(0, len(files), batch_size):
        batch = files[i:i + batch_size]
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
            result = chat_with_tool(
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
            user_msg_fallback = (
                "Classify each file below with 2-5 tags. "
                "Return a JSON object mapping the file number (as string) "
                "to an array of tags.\n"
                'Example: {"1": ["python-script", "development"]}\n\n'
                + "\n".join(file_descriptions)
            )
            text = chat(
                CLASSIFY_SYSTEM + "\nReturn ONLY a JSON object.",
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


# ------------------------------------------------------------------
# Fallback parsers (used when tool_use fails)
# ------------------------------------------------------------------

def _parse_tags(text: str) -> list[str]:
    try:
        tags = json.loads(text)
        if isinstance(tags, list):
            return [str(t).lower().strip() for t in tags if t]
    except json.JSONDecodeError:
        pass
    tags = []
    for part in text.replace("[", "").replace("]", "").replace('"', "").split(","):
        tag = part.strip().lower()
        if tag and len(tag) < 50:
            tags.append(tag)
    return tags[:5]


def _parse_batch_tags(text: str) -> dict[str, list[str]]:
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
