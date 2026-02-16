"""Tests for the undo/safety system."""

import json
import pytest
from pathlib import Path
from datetime import datetime, timedelta

from src.undo import (
    load_manifest,
    save_manifest,
    record_deletion,
    record_batch_deletion,
    get_recent_deletions,
    purge_expired,
    get_deletion_summary,
    find_recoverable,
    MANIFEST_FILE,
)


@pytest.fixture
def manifest_dir(tmp_path):
    """Provide a temp directory for manifest files."""
    d = tmp_path / "manifest"
    d.mkdir()
    return str(d)


class TestManifest:
    def test_load_empty(self, manifest_dir):
        """Loading nonexistent manifest returns empty list."""
        result = load_manifest(manifest_dir)
        assert result == []

    def test_save_and_load(self, manifest_dir):
        """Saving and loading round-trips correctly."""
        entries = [
            {"original_path": "/test/file.txt", "size_bytes": 1000, "deleted_at": "2025-01-01T00:00:00"}
        ]
        save_manifest(entries, manifest_dir)
        loaded = load_manifest(manifest_dir)
        assert len(loaded) == 1
        assert loaded[0]["original_path"] == "/test/file.txt"

    def test_load_corrupt_json(self, manifest_dir):
        """Corrupt JSON returns empty list."""
        path = Path(manifest_dir) / MANIFEST_FILE
        path.write_text("not valid json{{{")
        result = load_manifest(manifest_dir)
        assert result == []


class TestRecordDeletion:
    def test_record_single(self, manifest_dir):
        """Records a single deletion."""
        record_deletion("/test/file.txt", 5000, "hash123", manifest_dir=manifest_dir)

        entries = load_manifest(manifest_dir)
        assert len(entries) == 1
        assert entries[0]["original_path"] == "/test/file.txt"
        assert entries[0]["size_bytes"] == 5000
        assert entries[0]["content_hash"] == "hash123"
        assert entries[0]["reason"] == "duplicate_cleanup"
        assert "deleted_at" in entries[0]
        assert "expires_at" in entries[0]

    def test_record_multiple(self, manifest_dir):
        """Recording multiple deletions appends."""
        record_deletion("/test/a.txt", 100, manifest_dir=manifest_dir)
        record_deletion("/test/b.txt", 200, manifest_dir=manifest_dir)

        entries = load_manifest(manifest_dir)
        assert len(entries) == 2

    def test_record_batch(self, manifest_dir):
        """Batch recording adds all files."""
        files = [
            {"path": "/test/a.txt", "size_bytes": 100, "content_hash": "h1"},
            {"path": "/test/b.txt", "size_bytes": 200, "content_hash": "h2"},
            {"path": "/test/c.txt", "size_bytes": 300},
        ]
        record_batch_deletion(files, reason="test", manifest_dir=manifest_dir)

        entries = load_manifest(manifest_dir)
        assert len(entries) == 3
        assert all(e["reason"] == "test" for e in entries)

    def test_custom_reason(self, manifest_dir):
        """Custom reason is stored."""
        record_deletion("/test/file.txt", 100, reason="manual_cleanup", manifest_dir=manifest_dir)
        entries = load_manifest(manifest_dir)
        assert entries[0]["reason"] == "manual_cleanup"


class TestRecentDeletions:
    def test_get_recent(self, manifest_dir):
        """Recent deletions within window are returned."""
        record_deletion("/test/recent.txt", 100, manifest_dir=manifest_dir)

        recent = get_recent_deletions(days=30, manifest_dir=manifest_dir)
        assert len(recent) == 1

    def test_old_deletions_excluded(self, manifest_dir):
        """Old deletions outside window are excluded."""
        entries = [{
            "original_path": "/test/old.txt",
            "size_bytes": 100,
            "deleted_at": (datetime.now() - timedelta(days=60)).isoformat(),
            "expires_at": (datetime.now() - timedelta(days=30)).isoformat(),
        }]
        save_manifest(entries, manifest_dir)

        recent = get_recent_deletions(days=30, manifest_dir=manifest_dir)
        assert len(recent) == 0


class TestPurgeExpired:
    def test_purge_removes_expired(self, manifest_dir):
        """Expired entries are removed."""
        now = datetime.now()
        entries = [
            {
                "original_path": "/test/active.txt",
                "size_bytes": 100,
                "deleted_at": now.isoformat(),
                "expires_at": (now + timedelta(days=30)).isoformat(),
            },
            {
                "original_path": "/test/expired.txt",
                "size_bytes": 200,
                "deleted_at": (now - timedelta(days=60)).isoformat(),
                "expires_at": (now - timedelta(days=30)).isoformat(),
            },
        ]
        save_manifest(entries, manifest_dir)

        removed = purge_expired(manifest_dir)
        assert removed == 1

        remaining = load_manifest(manifest_dir)
        assert len(remaining) == 1
        assert remaining[0]["original_path"] == "/test/active.txt"

    def test_purge_empty(self, manifest_dir):
        """Purging empty manifest returns 0."""
        removed = purge_expired(manifest_dir)
        assert removed == 0


class TestDeletionSummary:
    def test_empty_summary(self, manifest_dir):
        """Summary of empty manifest."""
        summary = get_deletion_summary(manifest_dir)
        assert summary["total_deleted"] == 0
        assert summary["total_bytes"] == 0

    def test_summary_with_data(self, manifest_dir):
        """Summary reflects recorded deletions."""
        record_deletion("/test/a.txt", 1000, manifest_dir=manifest_dir)
        record_deletion("/test/b.txt", 2000, manifest_dir=manifest_dir)

        summary = get_deletion_summary(manifest_dir)
        assert summary["total_deleted"] == 2
        assert summary["total_bytes"] == 3000
        assert summary["recent_count"] == 2


class TestFindRecoverable:
    def test_no_db(self, manifest_dir):
        """Returns None when no db provided."""
        result = find_recoverable("hash123", db=None, manifest_dir=manifest_dir)
        assert result is None

    def test_no_hash(self, manifest_dir):
        """Returns None when no hash provided."""
        result = find_recoverable("", db=None, manifest_dir=manifest_dir)
        assert result is None

    def test_with_matching_file(self, db_path, tmp_path, manifest_dir):
        """Finds recoverable file with same hash."""
        from src.storage import FileDatabase
        from src.scanner import FileInfo

        # Create a real file
        real_file = tmp_path / "keeper.txt"
        real_file.write_text("content")

        db = FileDatabase(db_path)
        db.insert_file(FileInfo(
            path=str(real_file),
            name="keeper.txt",
            extension=".txt",
            size_bytes=7,
            created_at=datetime.now(),
            modified_at=datetime.now(),
            content_hash="hash_match",
            category="test",
        ))

        result = find_recoverable("hash_match", db=db, manifest_dir=manifest_dir)
        assert result == str(real_file)
        db.close()

    def test_no_matching_file(self, db_path, manifest_dir):
        """Returns None when no file with matching hash exists."""
        from src.storage import FileDatabase

        db = FileDatabase(db_path)
        result = find_recoverable("nonexistent_hash", db=db, manifest_dir=manifest_dir)
        assert result is None
        db.close()
