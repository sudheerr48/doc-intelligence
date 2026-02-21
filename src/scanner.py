"""Backward-compatible re-exports — use src.scanner.engine / src.core.models instead."""
from src.core.models import FileInfo, ScanResult  # noqa: F401
from src.scanner.engine import (  # noqa: F401
    compute_hash,
    should_skip,
    scan_folder_incremental,
    scan_folder_parallel,
    _collect_files_with_stats,
    NUM_WORKERS,
)
