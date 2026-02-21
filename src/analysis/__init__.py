"""
Analysis package — health scoring, duplicate management, image dedup, undo.
"""

from .health import compute_health_score, generate_health_text
from .duplicates import (
    STAGING_FOLDER,
    pick_keeper,
    stage_files,
    auto_stage_duplicates,
    list_staged_files,
    confirm_delete_staged,
    restore_staged_files,
)
from .undo import (
    record_deletion,
    record_batch_deletion,
    get_recent_deletions,
    purge_expired,
    get_deletion_summary,
    find_recoverable,
)

__all__ = [
    "compute_health_score",
    "generate_health_text",
    "STAGING_FOLDER",
    "pick_keeper",
    "stage_files",
    "auto_stage_duplicates",
    "list_staged_files",
    "confirm_delete_staged",
    "restore_staged_files",
    "record_deletion",
    "record_batch_deletion",
    "get_recent_deletions",
    "purge_expired",
    "get_deletion_summary",
    "find_recoverable",
]
