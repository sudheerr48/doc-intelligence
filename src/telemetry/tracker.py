"""
Privacy-respecting telemetry tracker.

Events are stored locally in a JSON-lines file.
No data is sent externally unless Sentry is explicitly configured.
"""

import json
import platform
import time
from pathlib import Path
from typing import Optional


_TELEMETRY_DIR = Path.home() / ".config" / "doc-intelligence"
_EVENTS_FILE = _TELEMETRY_DIR / "telemetry.jsonl"
_PREFS_FILE = _TELEMETRY_DIR / "telemetry_prefs.json"


# ------------------------------------------------------------------
# Opt-in / opt-out
# ------------------------------------------------------------------

def _load_prefs() -> dict:
    if _PREFS_FILE.exists():
        try:
            return json.loads(_PREFS_FILE.read_text())
        except Exception:
            pass
    return {"enabled": False}


def _save_prefs(prefs: dict):
    _TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)
    _PREFS_FILE.write_text(json.dumps(prefs, indent=2))


def is_telemetry_enabled() -> bool:
    """Check if telemetry is enabled (default: False)."""
    return _load_prefs().get("enabled", False)


def enable_telemetry():
    """Opt in to anonymous usage analytics."""
    prefs = _load_prefs()
    prefs["enabled"] = True
    prefs["opted_in_at"] = time.time()
    _save_prefs(prefs)


def disable_telemetry():
    """Opt out of analytics and remove stored events."""
    prefs = _load_prefs()
    prefs["enabled"] = False
    prefs["opted_out_at"] = time.time()
    _save_prefs(prefs)
    # Remove collected events
    if _EVENTS_FILE.exists():
        _EVENTS_FILE.unlink()


# ------------------------------------------------------------------
# Event tracking
# ------------------------------------------------------------------

def track_event(
    event: str,
    properties: Optional[dict] = None,
):
    """Track a named event with optional properties.

    Events are only stored if telemetry is enabled.
    No file names, paths, or content are ever included.

    Args:
        event: Event name (e.g. "scan_completed", "search_performed").
        properties: Optional dict of numeric/string properties.
                    Must NOT contain file paths or personal data.
    """
    if not is_telemetry_enabled():
        return

    record = {
        "event": event,
        "timestamp": time.time(),
        "platform": platform.system(),
        "version": _get_version(),
    }
    if properties:
        # Strip any accidentally included paths
        safe_props = {
            k: v for k, v in properties.items()
            if not isinstance(v, str) or (
                "/" not in v and "\\" not in v and "@" not in v
            )
        }
        record["properties"] = safe_props

    _append_event(record)


def track_error(
    error_type: str,
    error_message: str,
    context: Optional[str] = None,
):
    """Track an error for crash reporting.

    Args:
        error_type: Exception class name.
        error_message: Error message (sanitized — no paths).
        context: Which command/feature triggered the error.
    """
    if not is_telemetry_enabled():
        return

    record = {
        "event": "error",
        "timestamp": time.time(),
        "platform": platform.system(),
        "version": _get_version(),
        "error_type": error_type,
        "error_message": _sanitize(error_message),
        "context": context,
    }
    _append_event(record)

    # Forward to Sentry if configured
    _sentry_capture(error_type, error_message, context)


# ------------------------------------------------------------------
# Local stats
# ------------------------------------------------------------------

def get_local_stats() -> dict:
    """Return aggregate stats from local telemetry log."""
    if not _EVENTS_FILE.exists():
        return {"total_events": 0, "event_counts": {}, "errors": 0}

    event_counts: dict[str, int] = {}
    error_count = 0
    total = 0

    for line in _EVENTS_FILE.read_text().strip().split("\n"):
        if not line:
            continue
        try:
            record = json.loads(line)
            event = record.get("event", "unknown")
            event_counts[event] = event_counts.get(event, 0) + 1
            if event == "error":
                error_count += 1
            total += 1
        except json.JSONDecodeError:
            continue

    return {
        "total_events": total,
        "event_counts": event_counts,
        "errors": error_count,
    }


# ------------------------------------------------------------------
# Internals
# ------------------------------------------------------------------

def _append_event(record: dict):
    """Append a record to the local event log."""
    _TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)
    with open(_EVENTS_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")


def _sanitize(text: str) -> str:
    """Remove potential file paths and personal data from error messages."""
    import re
    # Remove anything that looks like a file path
    text = re.sub(r"[/\\][\w./\\-]+", "<path>", text)
    # Remove email-like patterns
    text = re.sub(r"\S+@\S+", "<email>", text)
    return text[:500]  # Truncate long messages


def _get_version() -> str:
    try:
        from importlib.metadata import version
        return version("doc-intelligence")
    except Exception:
        return "5.0.0"


def _sentry_capture(error_type: str, message: str, context: Optional[str]):
    """Forward error to Sentry if SDK is installed and DSN is configured."""
    try:
        import sentry_sdk
        if sentry_sdk.Hub.current.client:
            with sentry_sdk.push_scope() as scope:
                if context:
                    scope.set_tag("context", context)
                sentry_sdk.capture_message(
                    f"{error_type}: {message}", level="error"
                )
    except ImportError:
        pass
    except Exception:
        pass
