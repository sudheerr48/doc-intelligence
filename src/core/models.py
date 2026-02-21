"""
Core data models used across the application.
"""

from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass, asdict


@dataclass
class FileInfo:
    """Information about a scanned file."""
    path: str
    name: str
    extension: str
    size_bytes: int
    created_at: datetime
    modified_at: datetime
    content_hash: Optional[str] = None
    category: Optional[str] = None
    content_text: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScanResult:
    """Result of scanning a folder."""
    new_files: List[FileInfo]
    unchanged_count: int
    removed_count: int
    total_size: int
