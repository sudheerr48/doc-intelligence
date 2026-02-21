"""
Filesystem watcher — handles real-time file events and updates the database.
"""

from pathlib import Path
from datetime import datetime
from typing import Optional

from watchdog.events import FileSystemEventHandler, FileSystemEvent

from src.core.models import FileInfo
from src.core.database import FileDatabase
from src.scanner.engine import compute_hash, should_skip
from src.scanner.extractors import extract_text


class FileChangeHandler(FileSystemEventHandler):
    """Watchdog event handler that updates the DuckDB database on file events."""

    def __init__(
        self,
        db: FileDatabase,
        category: str = "watched",
        exclude_patterns: Optional[list] = None,
        min_size_bytes: int = 0,
        hash_algorithm: str = "xxhash",
        on_event_callback=None,
    ):
        super().__init__()
        self.db = db
        self.category = category
        self.exclude_patterns = exclude_patterns or []
        self.min_size_bytes = min_size_bytes
        self.hash_algorithm = hash_algorithm
        self.on_event_callback = on_event_callback

    def _should_process(self, path: str) -> bool:
        p = Path(path)
        if p.is_dir():
            return False
        if should_skip(p, self.exclude_patterns):
            return False
        if p.is_symlink():
            return False
        return True

    def _build_file_info(self, path: str) -> Optional[FileInfo]:
        p = Path(path)
        try:
            stat = p.stat()
        except (OSError, PermissionError):
            return None
        if stat.st_size < self.min_size_bytes:
            return None
        content_hash = compute_hash(path, self.hash_algorithm)
        content_text = extract_text(path)
        return FileInfo(
            path=path,
            name=p.name,
            extension=p.suffix.lower(),
            size_bytes=stat.st_size,
            created_at=datetime.fromtimestamp(stat.st_ctime),
            modified_at=datetime.fromtimestamp(stat.st_mtime),
            content_hash=content_hash,
            category=self.category,
            content_text=content_text,
        )

    def _notify(self, event_type: str, path: str):
        if self.on_event_callback:
            self.on_event_callback(event_type, path)

    def on_created(self, event: FileSystemEvent):
        if event.is_directory or not self._should_process(event.src_path):
            return
        fi = self._build_file_info(event.src_path)
        if fi:
            self.db.insert_file(fi)
            self._notify("created", event.src_path)

    def on_modified(self, event: FileSystemEvent):
        if event.is_directory or not self._should_process(event.src_path):
            return
        fi = self._build_file_info(event.src_path)
        if fi:
            self.db.insert_file(fi)
            self._notify("modified", event.src_path)

    def on_deleted(self, event: FileSystemEvent):
        if event.is_directory:
            return
        path = event.src_path
        if should_skip(Path(path), self.exclude_patterns):
            return
        self.db.conn.execute("DELETE FROM files WHERE path = ?", [path])
        self._notify("deleted", path)

    def on_moved(self, event: FileSystemEvent):
        if event.is_directory:
            return
        self.db.conn.execute(
            "DELETE FROM files WHERE path = ?", [event.src_path]
        )
        if self._should_process(event.dest_path):
            fi = self._build_file_info(event.dest_path)
            if fi:
                self.db.insert_file(fi)
        self._notify("moved", f"{event.src_path} -> {event.dest_path}")
