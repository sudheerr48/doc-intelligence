"""
Optional, privacy-respecting analytics and crash reporting.

Principles:
  - OFF by default — requires explicit opt-in
  - Never collects file names, paths, or content
  - Only tracks: feature usage counts, error types, scan stats
  - Local log for self-hosted analytics
  - Optional Sentry integration for crash reports

Enable in config:
    telemetry:
      enabled: true
      sentry_dsn: "https://..."  # optional
"""

from .tracker import (
    track_event,
    track_error,
    is_telemetry_enabled,
    enable_telemetry,
    disable_telemetry,
    get_local_stats,
)

__all__ = [
    "track_event",
    "track_error",
    "is_telemetry_enabled",
    "enable_telemetry",
    "disable_telemetry",
    "get_local_stats",
]
