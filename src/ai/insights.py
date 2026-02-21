"""
AI-powered health insights generation.
"""

import json
from typing import Optional

from .providers import chat, chat_with_tool, default_model


HEALTH_SYSTEM = """\
You are a file system health analyst. Given metrics about a user's indexed files, \
provide a concise health report with actionable recommendations.

Be specific with numbers. Reference actual file names and sizes when relevant.\
"""

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
                    "severity": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                    },
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


def generate_health_insights(
    metrics: dict, model: Optional[str] = None,
) -> dict:
    """Generate AI-powered health insights from file system metrics."""
    metrics_text = json.dumps(metrics, indent=2, default=str)

    try:
        return chat_with_tool(
            system=HEALTH_SYSTEM,
            user_msg=f"Analyze these file system metrics:\n\n{metrics_text}",
            model=default_model(model),
            max_tokens=1000,
            tool_name="health_report",
            tool_description="Generate a file system health report",
            tool_schema=_HEALTH_TOOL_SCHEMA,
        )
    except Exception:
        text = chat(
            HEALTH_SYSTEM + (
                '\nFormat your response as a JSON object with keys: '
                '"score" (int 0-100), "grade" (string), "summary" (string), '
                '"issues" (array), "recommendations" (array).'
            ),
            f"Analyze these file system metrics:\n\n{metrics_text}",
            default_model(model),
            max_tokens=1000,
        )
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [ln for ln in lines if not ln.startswith("```")]
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
