"""
Tests for src/watcher.py - file watcher event handlers.
Tests the handler logic directly without needing actual filesystem monitoring.
"""

import os
import time
from pathlib import Path
from datetime import datetime

import pytest
from watchdog.events import (
    FileCreatedEvent,
    FileModifiedEvent,
    FileDeletedEvent,
    FileMovedEvent,
    DirCreatedEvent,
)

from src.core.database import FileDatabase
from src.scanner.watcher import FileChangeHandler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def watch_db(tmp_path):
    """Provide a FileDatabase for watcher tests."""
    db = FileDatabase(str(tmp_path / "watch.duckdb"))
    yield db
    db.close()


@pytest.fixture
def handler(watch_db):
    """Create a FileChangeHandler with event tracking."""
    events = []

    def track(event_type, path):
        events.append((event_type, path))

    h = FileChangeHandler(
        db=watch_db,
        category="test",
        exclude_patterns=["__pycache__", "*.pyc"],
        min_size_bytes=1,
        on_event_callback=track,
    )
    h._events = events  # attach for assertions
    return h


def count_rows(db):
    return db.conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]


# ---------------------------------------------------------------------------
# on_created
# ---------------------------------------------------------------------------

class TestOnCreated:
    """Tests for file creation events."""

    def test_creates_db_entry(self, handler, watch_db, tmp_path):
        f = tmp_path / "new_file.txt"
        f.write_text("hello world")

        event = FileCreatedEvent(str(f))
        handler.on_created(event)

        assert count_rows(watch_db) == 1
        row = watch_db.conn.execute("SELECT name, category FROM files").fetchone()
        assert row[0] == "new_file.txt"
        assert row[1] == "test"

    def test_extracts_content_text(self, handler, watch_db, tmp_path):
        f = tmp_path / "doc.txt"
        f.write_text("important document content")

        event = FileCreatedEvent(str(f))
        handler.on_created(event)

        row = watch_db.conn.execute("SELECT content_text FROM files").fetchone()
        assert "important document content" in row[0]

    def test_computes_hash(self, handler, watch_db, tmp_path):
        f = tmp_path / "hashed.txt"
        f.write_text("hash me")

        event = FileCreatedEvent(str(f))
        handler.on_created(event)

        row = watch_db.conn.execute("SELECT content_hash FROM files").fetchone()
        assert row[0] is not None
        assert len(row[0]) > 0

    def test_ignores_excluded_pattern(self, handler, watch_db, tmp_path):
        f = tmp_path / "__pycache__" / "module.pyc"
        f.parent.mkdir()
        f.write_bytes(b"\x00" * 100)

        event = FileCreatedEvent(str(f))
        handler.on_created(event)

        assert count_rows(watch_db) == 0

    def test_ignores_directory_events(self, handler, watch_db, tmp_path):
        d = tmp_path / "newdir"
        d.mkdir()

        event = DirCreatedEvent(str(d))
        handler.on_created(event)

        assert count_rows(watch_db) == 0

    def test_ignores_files_below_min_size(self, handler, watch_db, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("")  # 0 bytes, below min_size_bytes=1

        event = FileCreatedEvent(str(f))
        handler.on_created(event)

        assert count_rows(watch_db) == 0

    def test_fires_callback(self, handler, tmp_path):
        f = tmp_path / "tracked.txt"
        f.write_text("content")

        event = FileCreatedEvent(str(f))
        handler.on_created(event)

        assert len(handler._events) == 1
        assert handler._events[0][0] == "created"


# ---------------------------------------------------------------------------
# on_modified
# ---------------------------------------------------------------------------

class TestOnModified:
    """Tests for file modification events."""

    def test_updates_existing_entry(self, handler, watch_db, tmp_path):
        f = tmp_path / "changing.txt"
        f.write_text("version 1")

        # Create entry
        handler.on_created(FileCreatedEvent(str(f)))
        hash_v1 = watch_db.conn.execute("SELECT content_hash FROM files").fetchone()[0]

        # Modify file
        f.write_text("version 2 with different content")
        handler.on_modified(FileModifiedEvent(str(f)))

        # Should still be one row, but hash updated
        assert count_rows(watch_db) == 1
        hash_v2 = watch_db.conn.execute("SELECT content_hash FROM files").fetchone()[0]
        assert hash_v2 != hash_v1

    def test_creates_entry_if_not_exists(self, handler, watch_db, tmp_path):
        f = tmp_path / "new_via_modify.txt"
        f.write_text("appeared")

        handler.on_modified(FileModifiedEvent(str(f)))
        assert count_rows(watch_db) == 1


# ---------------------------------------------------------------------------
# on_deleted
# ---------------------------------------------------------------------------

class TestOnDeleted:
    """Tests for file deletion events."""

    def test_removes_db_entry(self, handler, watch_db, tmp_path):
        f = tmp_path / "to_delete.txt"
        f.write_text("goodbye")

        handler.on_created(FileCreatedEvent(str(f)))
        assert count_rows(watch_db) == 1

        # Delete the file
        f.unlink()
        handler.on_deleted(FileDeletedEvent(str(f)))
        assert count_rows(watch_db) == 0

    def test_delete_nonexistent_is_safe(self, handler, watch_db):
        """Deleting a file not in DB should not error."""
        handler.on_deleted(FileDeletedEvent("/no/such/file.txt"))
        assert count_rows(watch_db) == 0

    def test_fires_callback(self, handler, tmp_path):
        f = tmp_path / "del.txt"
        f.write_text("x")
        handler.on_created(FileCreatedEvent(str(f)))
        handler._events.clear()

        f.unlink()
        handler.on_deleted(FileDeletedEvent(str(f)))

        assert len(handler._events) == 1
        assert handler._events[0][0] == "deleted"


# ---------------------------------------------------------------------------
# on_moved
# ---------------------------------------------------------------------------

class TestOnMoved:
    """Tests for file move/rename events."""

    def test_updates_path_on_move(self, handler, watch_db, tmp_path):
        src = tmp_path / "old_name.txt"
        dst = tmp_path / "new_name.txt"
        src.write_text("moving file")

        handler.on_created(FileCreatedEvent(str(src)))
        assert count_rows(watch_db) == 1

        # Simulate move
        src.rename(dst)
        handler.on_moved(FileMovedEvent(str(src), str(dst)))

        assert count_rows(watch_db) == 1
        row = watch_db.conn.execute("SELECT path, name FROM files").fetchone()
        assert row[0] == str(dst)
        assert row[1] == "new_name.txt"

    def test_move_to_excluded_removes(self, handler, watch_db, tmp_path):
        src = tmp_path / "good.txt"
        src.write_text("content")
        handler.on_created(FileCreatedEvent(str(src)))
        assert count_rows(watch_db) == 1

        # Move to excluded location
        pycache = tmp_path / "__pycache__"
        pycache.mkdir()
        dst = pycache / "good.pyc"
        src.rename(dst)
        handler.on_moved(FileMovedEvent(str(src), str(dst)))

        # Should be removed since dest is excluded
        assert count_rows(watch_db) == 0


# ---------------------------------------------------------------------------
# Integration
# ---------------------------------------------------------------------------

class TestWatcherIntegration:
    """Integration tests for the full watcher flow."""

    def test_create_modify_delete_cycle(self, handler, watch_db, tmp_path):
        f = tmp_path / "lifecycle.txt"

        # Create
        f.write_text("initial")
        handler.on_created(FileCreatedEvent(str(f)))
        assert count_rows(watch_db) == 1

        # Modify
        f.write_text("updated")
        handler.on_modified(FileModifiedEvent(str(f)))
        assert count_rows(watch_db) == 1

        # Delete
        f.unlink()
        handler.on_deleted(FileDeletedEvent(str(f)))
        assert count_rows(watch_db) == 0

    def test_multiple_files(self, handler, watch_db, tmp_path):
        for i in range(5):
            f = tmp_path / f"file_{i}.txt"
            f.write_text(f"content {i}")
            handler.on_created(FileCreatedEvent(str(f)))

        assert count_rows(watch_db) == 5

        # Delete 2
        for i in range(2):
            f = tmp_path / f"file_{i}.txt"
            f.unlink()
            handler.on_deleted(FileDeletedEvent(str(f)))

        assert count_rows(watch_db) == 3


# ---------------------------------------------------------------------------
# CLI smoke tests
# ---------------------------------------------------------------------------

class TestWatchCLI:
    """Smoke tests for the watch CLI."""

    def test_watch_help(self):
        from typer.testing import CliRunner
        from scripts.watch import app

        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "--path" in result.output

    def test_unified_cli_watch_help(self):
        from typer.testing import CliRunner
        from scripts.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["watch", "--help"])
        assert result.exit_code == 0
        assert "--path" in result.output
        assert "--category" in result.output
