"""Backward-compatible re-exports — use src.analysis.undo instead."""
from src.analysis.undo import (  # noqa: F401
    load_manifest,
    save_manifest,
    record_deletion,
    record_batch_deletion,
    get_recent_deletions,
    purge_expired,
    find_recoverable,
    get_deletion_summary,
)
