"""
Tests for src/storage.py
"""

import os
from pathlib import Path
from datetime import datetime

import pytest

from src.scanner import FileInfo
from src.storage import FileDatabase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_file_info(
    path="/tmp/test/file.txt",
    name="file.txt",
    extension=".txt",
    size_bytes=1024,
    content_hash="abc123",
    category="test",
):
    """Create a FileInfo with sensible defaults for testing."""
    return FileInfo(
        path=path,
        name=name,
        extension=extension,
        size_bytes=size_bytes,
        created_at=datetime(2024, 1, 1, 12, 0, 0),
        modified_at=datetime(2024, 1, 1, 12, 0, 0),
        content_hash=content_hash,
        category=category,
    )


# ---------------------------------------------------------------------------
# FileDatabase basic operations
# ---------------------------------------------------------------------------

class TestFileDatabaseInit:
    """Tests for database initialization."""

    def test_creates_database_file(self, db_path):
        db = FileDatabase(db_path)
        assert Path(db_path).exists()
        db.close()

    def test_creates_parent_directories(self, tmp_path):
        db_path = str(tmp_path / "nested" / "dir" / "test.duckdb")
        db = FileDatabase(db_path)
        assert Path(db_path).exists()
        db.close()

    def test_creates_tables_and_indexes(self, db_path):
        db = FileDatabase(db_path)
        # Verify the files table exists by running a query
        result = db.conn.execute("SELECT COUNT(*) FROM files").fetchone()
        assert result[0] == 0
        db.close()


# ---------------------------------------------------------------------------
# insert_file / insert_batch
# ---------------------------------------------------------------------------

class TestInsertOperations:
    """Tests for insert_file and insert_batch."""

    def test_insert_single_file(self, db_path):
        db = FileDatabase(db_path)
        fi = make_file_info()
        assert db.insert_file(fi) is True

        rows = db.conn.execute("SELECT * FROM files").fetchall()
        assert len(rows) == 1
        db.close()

    def test_insert_upsert_same_path(self, db_path):
        db = FileDatabase(db_path)
        fi1 = make_file_info(content_hash="hash_v1")
        fi2 = make_file_info(content_hash="hash_v2")  # same path, different hash

        db.insert_file(fi1)
        db.insert_file(fi2)

        rows = db.conn.execute("SELECT content_hash FROM files").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "hash_v2"
        db.close()

    def test_insert_batch(self, db_path):
        db = FileDatabase(db_path)
        files = [
            make_file_info(path=f"/tmp/test/file{i}.txt", name=f"file{i}.txt", content_hash=f"hash{i}")
            for i in range(10)
        ]
        count = db.insert_batch(files)
        assert count == 10

        total = db.conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        assert total == 10
        db.close()

    def test_insert_batch_empty_list(self, db_path):
        db = FileDatabase(db_path)
        count = db.insert_batch([])
        assert count == 0
        db.close()


# ---------------------------------------------------------------------------
# get_duplicates
# ---------------------------------------------------------------------------

class TestGetDuplicates:
    """Tests for duplicate detection."""

    def test_no_duplicates(self, db_path):
        db = FileDatabase(db_path)
        db.insert_file(make_file_info(path="/a.txt", content_hash="hash1"))
        db.insert_file(make_file_info(path="/b.txt", content_hash="hash2"))
        db.insert_file(make_file_info(path="/c.txt", content_hash="hash3"))

        dups = db.get_duplicates()
        assert len(dups) == 0
        db.close()

    def test_finds_duplicates(self, db_path):
        db = FileDatabase(db_path)
        # 3 files with the same hash
        db.insert_file(make_file_info(path="/a.txt", name="a.txt", content_hash="dup_hash", size_bytes=100))
        db.insert_file(make_file_info(path="/b.txt", name="b.txt", content_hash="dup_hash", size_bytes=100))
        db.insert_file(make_file_info(path="/c.txt", name="c.txt", content_hash="dup_hash", size_bytes=100))
        # 1 unique file
        db.insert_file(make_file_info(path="/d.txt", name="d.txt", content_hash="unique_hash", size_bytes=200))

        dups = db.get_duplicates()
        assert len(dups) == 1
        assert dups[0]["hash"] == "dup_hash"
        assert dups[0]["count"] == 3
        assert set(dups[0]["paths"]) == {"/a.txt", "/b.txt", "/c.txt"}
        db.close()

    def test_multiple_duplicate_groups(self, db_path):
        db = FileDatabase(db_path)
        # Group 1: 2 duplicates
        db.insert_file(make_file_info(path="/g1a.txt", content_hash="group1", size_bytes=500))
        db.insert_file(make_file_info(path="/g1b.txt", content_hash="group1", size_bytes=500))
        # Group 2: 3 duplicates
        db.insert_file(make_file_info(path="/g2a.txt", content_hash="group2", size_bytes=200))
        db.insert_file(make_file_info(path="/g2b.txt", content_hash="group2", size_bytes=200))
        db.insert_file(make_file_info(path="/g2c.txt", content_hash="group2", size_bytes=200))

        dups = db.get_duplicates()
        assert len(dups) == 2
        db.close()

    def test_wasted_size_calculation(self, db_path):
        db = FileDatabase(db_path)
        # 3 files, 100 bytes each = 300 total, 200 wasted
        db.insert_file(make_file_info(path="/a.txt", content_hash="hash", size_bytes=100))
        db.insert_file(make_file_info(path="/b.txt", content_hash="hash", size_bytes=100))
        db.insert_file(make_file_info(path="/c.txt", content_hash="hash", size_bytes=100))

        dups = db.get_duplicates()
        assert len(dups) == 1
        assert dups[0]["total_size"] == 300
        assert dups[0]["wasted_size"] == 200  # 300 - (300 // 3)
        db.close()

    def test_null_hash_excluded(self, db_path):
        db = FileDatabase(db_path)
        db.insert_file(make_file_info(path="/a.txt", content_hash=None))
        db.insert_file(make_file_info(path="/b.txt", content_hash=None))

        dups = db.get_duplicates()
        assert len(dups) == 0
        db.close()


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------

class TestGetStats:
    """Tests for database statistics."""

    def test_empty_db_stats(self, db_path):
        db = FileDatabase(db_path)
        stats = db.get_stats()
        assert stats["total_files"] == 0
        assert stats["total_size_bytes"] == 0
        assert stats["by_category"] == {}
        assert stats["by_extension"] == {}
        assert stats["duplicate_sets"] == 0
        db.close()

    def test_stats_after_inserts(self, db_path):
        db = FileDatabase(db_path)
        db.insert_file(make_file_info(path="/a.txt", extension=".txt", size_bytes=100, category="docs"))
        db.insert_file(make_file_info(path="/b.csv", extension=".csv", size_bytes=200, category="docs"))
        db.insert_file(make_file_info(path="/c.jpg", extension=".jpg", size_bytes=300, category="images"))

        stats = db.get_stats()
        assert stats["total_files"] == 3
        assert stats["total_size_bytes"] == 600
        assert stats["by_category"]["docs"] == 2
        assert stats["by_category"]["images"] == 1
        assert stats["by_extension"][".txt"] == 1
        assert stats["by_extension"][".csv"] == 1
        assert stats["by_extension"][".jpg"] == 1
        db.close()

    def test_stats_counts_duplicate_sets(self, db_path):
        db = FileDatabase(db_path)
        db.insert_file(make_file_info(path="/a.txt", content_hash="dup"))
        db.insert_file(make_file_info(path="/b.txt", content_hash="dup"))
        db.insert_file(make_file_info(path="/c.txt", content_hash="unique"))

        stats = db.get_stats()
        assert stats["duplicate_sets"] == 1
        db.close()


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

class TestSearch:
    """Tests for the search function."""

    def test_search_by_name(self, db_path):
        db = FileDatabase(db_path)
        db.insert_file(make_file_info(path="/docs/report.txt", name="report.txt"))
        db.insert_file(make_file_info(path="/docs/notes.csv", name="notes.csv", content_hash="h2"))
        db.insert_file(make_file_info(path="/imgs/photo.jpg", name="photo.jpg", content_hash="h3"))

        results = db.search("report")
        assert len(results) == 1
        assert results[0]["name"] == "report.txt"
        db.close()

    def test_search_case_insensitive(self, db_path):
        db = FileDatabase(db_path)
        db.insert_file(make_file_info(path="/docs/Report.TXT", name="Report.TXT"))

        results = db.search("report")
        assert len(results) == 1

        results = db.search("REPORT")
        assert len(results) == 1
        db.close()

    def test_search_by_path(self, db_path):
        db = FileDatabase(db_path)
        db.insert_file(make_file_info(path="/home/user/documents/tax_2023.pdf", name="tax_2023.pdf"))
        db.insert_file(make_file_info(path="/home/user/downloads/photo.jpg", name="photo.jpg", content_hash="h2"))

        results = db.search("documents")
        assert len(results) == 1
        assert results[0]["name"] == "tax_2023.pdf"
        db.close()

    def test_search_no_results(self, db_path):
        db = FileDatabase(db_path)
        db.insert_file(make_file_info(path="/a.txt", name="a.txt"))

        results = db.search("nonexistent")
        assert len(results) == 0
        db.close()

    def test_search_respects_limit(self, db_path):
        db = FileDatabase(db_path)
        for i in range(20):
            db.insert_file(make_file_info(
                path=f"/docs/file{i}.txt",
                name=f"file{i}.txt",
                content_hash=f"hash{i}",
            ))

        results = db.search("file", limit=5)
        assert len(results) == 5
        db.close()


# ---------------------------------------------------------------------------
# get_cached_file_info
# ---------------------------------------------------------------------------

class TestGetCachedFileInfo:
    """Tests for the incremental scanning cache."""

    def test_returns_cached_info(self, db_path):
        db = FileDatabase(db_path)
        fi = make_file_info(path="/a.txt", size_bytes=512, content_hash="myhash")
        db.insert_file(fi)

        cache = db.get_cached_file_info(["/a.txt"])
        assert "/a.txt" in cache
        assert cache["/a.txt"]["size_bytes"] == 512
        assert cache["/a.txt"]["content_hash"] == "myhash"
        assert cache["/a.txt"]["modified_at"] is not None
        db.close()

    def test_missing_paths_not_in_cache(self, db_path):
        db = FileDatabase(db_path)
        db.insert_file(make_file_info(path="/a.txt"))

        cache = db.get_cached_file_info(["/a.txt", "/missing.txt"])
        assert "/a.txt" in cache
        assert "/missing.txt" not in cache
        db.close()

    def test_empty_paths_returns_empty(self, db_path):
        db = FileDatabase(db_path)
        cache = db.get_cached_file_info([])
        assert cache == {}
        db.close()

    def test_large_batch_query(self, db_path):
        """Test that batching works for >500 paths."""
        db = FileDatabase(db_path)
        paths = []
        for i in range(600):
            path = f"/files/file{i}.txt"
            paths.append(path)
            db.insert_file(make_file_info(
                path=path, name=f"file{i}.txt", content_hash=f"hash{i}",
            ))

        cache = db.get_cached_file_info(paths)
        assert len(cache) == 600
        db.close()


# ---------------------------------------------------------------------------
# remove_missing_files
# ---------------------------------------------------------------------------

class TestRemoveMissingFiles:
    """Tests for cleanup of deleted files."""

    def test_removes_missing_files(self, db_path):
        db = FileDatabase(db_path)
        db.insert_file(make_file_info(path="/a.txt", content_hash="h1", category="docs"))
        db.insert_file(make_file_info(path="/b.txt", content_hash="h2", category="docs"))
        db.insert_file(make_file_info(path="/c.txt", content_hash="h3", category="docs"))

        # Only /a.txt still exists
        removed = db.remove_missing_files({"/a.txt"}, "docs")
        assert removed == 2

        total = db.conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        assert total == 1
        db.close()

    def test_no_removal_when_all_valid(self, db_path):
        db = FileDatabase(db_path)
        db.insert_file(make_file_info(path="/a.txt", content_hash="h1", category="docs"))
        db.insert_file(make_file_info(path="/b.txt", content_hash="h2", category="docs"))

        removed = db.remove_missing_files({"/a.txt", "/b.txt"}, "docs")
        assert removed == 0
        db.close()

    def test_only_removes_from_specified_category(self, db_path):
        db = FileDatabase(db_path)
        db.insert_file(make_file_info(path="/a.txt", content_hash="h1", category="docs"))
        db.insert_file(make_file_info(path="/b.txt", content_hash="h2", category="images"))

        # Remove missing from "docs" category — /b.txt is in "images" so untouched
        removed = db.remove_missing_files(set(), "docs")
        assert removed == 1

        total = db.conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        assert total == 1  # /b.txt still there
        db.close()


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------

class TestClear:
    """Tests for database clearing."""

    def test_clear_removes_all_data(self, db_path):
        db = FileDatabase(db_path)
        db.insert_file(make_file_info(path="/a.txt", content_hash="h1"))
        db.insert_file(make_file_info(path="/b.txt", content_hash="h2"))

        db.clear()

        total = db.conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        assert total == 0
        db.close()


# ---------------------------------------------------------------------------
# Integration: scan real temp files, insert to DB, find duplicates
# ---------------------------------------------------------------------------

class TestEndToEnd:
    """Integration test: scan -> store -> query duplicates."""

    def test_scan_and_find_duplicates(self, duplicate_files, db_path):
        """Full pipeline: scan duplicate_files fixture, store, find dups."""
        from src.scanner import scan_folder_parallel

        files = scan_folder_parallel(
            root_path=str(duplicate_files),
            category="test",
            min_size_bytes=1,
        )
        assert len(files) == 5

        db = FileDatabase(db_path)
        db.insert_batch(files)

        dups = db.get_duplicates()
        assert len(dups) == 1
        assert dups[0]["count"] == 3  # original + copy1 + copy2

        stats = db.get_stats()
        assert stats["total_files"] == 5
        assert stats["duplicate_sets"] == 1

        db.close()
