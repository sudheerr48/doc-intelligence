"""Backward-compatible re-exports — use src.analysis.duplicates instead."""
from src.analysis.duplicates import (  # noqa: F401
    STAGING_FOLDER,
    pick_keeper,
    stage_files,
    auto_stage_duplicates,
    list_staged_files,
    confirm_delete_staged,
    restore_staged_files,
)
