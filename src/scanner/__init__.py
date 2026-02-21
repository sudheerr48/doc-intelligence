"""
Scanner package — file discovery, hashing, text extraction, and filesystem watching.
"""

from .engine import (
    compute_hash,
    should_skip,
    scan_folder_incremental,
    scan_folder_parallel,
)
from .extractors import extract_text

__all__ = [
    "compute_hash",
    "should_skip",
    "scan_folder_incremental",
    "scan_folder_parallel",
    "extract_text",
]
