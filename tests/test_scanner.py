"""
Tests for src/scanner.py
"""

import os
import time
from pathlib import Path
from datetime import datetime

import pytest

from src.scanner import (
    compute_hash,
    should_skip,
    _collect_files_with_stats,
    scan_folder_incremental,
    scan_folder_parallel,
    FileInfo,
    ScanResult,
)


# ---------------------------------------------------------------------------
# compute_hash
# ---------------------------------------------------------------------------

class TestComputeHash:
    """Tests for the compute_hash function."""

    def test_xxhash_produces_hex_string(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        result = compute_hash(str(f), "xxhash")
        assert result is not None
        assert isinstance(result, str)
        assert len(result) == 16  # xxh64 produces 16 hex chars

    def test_sha256_produces_hex_string(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        result = compute_hash(str(f), "sha256")
        assert result is not None
        assert len(result) == 64  # SHA-256 produces 64 hex chars

    def test_md5_produces_hex_string(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        result = compute_hash(str(f), "md5")
        assert result is not None
        assert len(result) == 32  # MD5 produces 32 hex chars

    def test_same_content_same_hash(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("identical content")
        f2.write_text("identical content")
        assert compute_hash(str(f1), "xxhash") == compute_hash(str(f2), "xxhash")
        assert compute_hash(str(f1), "sha256") == compute_hash(str(f2), "sha256")

    def test_different_content_different_hash(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("content one")
        f2.write_text("content two")
        assert compute_hash(str(f1), "xxhash") != compute_hash(str(f2), "xxhash")

    def test_nonexistent_file_returns_none(self):
        result = compute_hash("/nonexistent/path/file.txt", "xxhash")
        assert result is None

    def test_empty_file_produces_hash(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("")
        result = compute_hash(str(f), "xxhash")
        assert result is not None

    def test_binary_file(self, tmp_path):
        f = tmp_path / "binary.bin"
        f.write_bytes(b"\x00\xff\x01\xfe" * 1000)
        result = compute_hash(str(f), "xxhash")
        assert result is not None


# ---------------------------------------------------------------------------
# should_skip
# ---------------------------------------------------------------------------

class TestShouldSkip:
    """Tests for the should_skip function."""

    def test_skip_dotfile_pattern(self):
        assert should_skip(Path("/some/path/.DS_Store"), [".DS_Store"]) is True

    def test_skip_extension_pattern(self):
        assert should_skip(Path("/some/path/file.pyc"), ["*.pyc"]) is True

    def test_skip_directory_name(self):
        assert should_skip(Path("/project/__pycache__/module.pyc"), ["__pycache__"]) is True

    def test_skip_node_modules(self):
        assert should_skip(Path("/project/node_modules/pkg/index.js"), ["node_modules"]) is True

    def test_no_skip_normal_file(self):
        assert should_skip(Path("/some/path/report.pdf"), [".DS_Store", "*.pyc", "__pycache__"]) is False

    def test_no_skip_empty_patterns(self):
        assert should_skip(Path("/any/file.txt"), []) is False

    def test_skip_git_directory(self):
        assert should_skip(Path("/project/.git/objects/abc"), [".git"]) is True

    def test_no_skip_partial_match(self):
        # "cache" should NOT match a file called "mycachefile.txt"
        # unless "cache" appears as a substring - current impl does substring match
        assert should_skip(Path("/data/mycachefile.txt"), [".cache"]) is False


# ---------------------------------------------------------------------------
# _collect_files_with_stats
# ---------------------------------------------------------------------------

class TestCollectFilesWithStats:
    """Tests for the _collect_files_with_stats function."""

    def test_collects_all_files(self, sample_files):
        files = _collect_files_with_stats(str(sample_files), [])
        paths = [f[0] for f in files]
        # Should include all files (including empty, tiny, and __pycache__)
        assert len(files) >= 8

    def test_excludes_pycache(self, sample_files):
        files = _collect_files_with_stats(str(sample_files), ["__pycache__"])
        paths = [f[0] for f in files]
        assert not any("__pycache__" in p for p in paths)

    def test_excludes_pyc_extension(self, sample_files):
        files = _collect_files_with_stats(str(sample_files), ["*.pyc"])
        paths = [f[0] for f in files]
        assert not any(p.endswith(".pyc") for p in paths)

    def test_include_extensions_filter(self, sample_files):
        files = _collect_files_with_stats(
            str(sample_files), [], include_extensions=[".txt"]
        )
        paths = [f[0] for f in files]
        assert all(p.endswith(".txt") for p in paths)
        # Should find: report.txt, empty.txt, tiny.txt
        assert len(paths) == 3

    def test_min_size_filter(self, sample_files):
        files = _collect_files_with_stats(
            str(sample_files), [], min_size_bytes=10
        )
        sizes = [f[1] for f in files]
        assert all(s >= 10 for s in sizes)
        # empty.txt (0 bytes) and tiny.txt (5 bytes) should be excluded
        paths = [f[0] for f in files]
        assert not any(p.endswith("empty.txt") for p in paths)
        assert not any(p.endswith("tiny.txt") for p in paths)

    def test_returns_tuples_of_path_size_mtime(self, sample_files):
        files = _collect_files_with_stats(str(sample_files), [])
        for item in files:
            assert len(item) == 3
            path, size, mtime = item
            assert isinstance(path, str)
            assert isinstance(size, int)
            assert isinstance(mtime, float)

    def test_nonexistent_directory_returns_empty(self):
        files = _collect_files_with_stats("/nonexistent/path", [])
        assert files == []

    def test_combined_filters(self, sample_files):
        files = _collect_files_with_stats(
            str(sample_files),
            exclude_patterns=["__pycache__"],
            include_extensions=[".txt", ".csv"],
            min_size_bytes=1,
        )
        paths = [f[0] for f in files]
        for p in paths:
            assert p.endswith(".txt") or p.endswith(".csv")
            assert "__pycache__" not in p


# ---------------------------------------------------------------------------
# scan_folder_incremental
# ---------------------------------------------------------------------------

class TestScanFolderIncremental:
    """Tests for incremental scanning logic."""

    def test_full_scan_no_cache(self, sample_files):
        """First scan with empty cache should find all qualifying files."""
        result = scan_folder_incremental(
            root_path=str(sample_files),
            category="test",
            cached_files={},
            exclude_patterns=["__pycache__"],
            min_size_bytes=1,
        )
        assert isinstance(result, ScanResult)
        assert len(result.new_files) > 0
        assert result.unchanged_count == 0
        assert result.removed_count == 0
        assert result.total_size > 0

        # All results should be FileInfo objects
        for f in result.new_files:
            assert isinstance(f, FileInfo)
            assert f.content_hash is not None
            assert f.category == "test"

    def test_incremental_scan_all_cached(self, sample_files):
        """Second scan with valid cache should find zero new files."""
        # First scan
        result1 = scan_folder_incremental(
            root_path=str(sample_files),
            category="test",
            cached_files={},
            exclude_patterns=["__pycache__"],
            min_size_bytes=1,
        )

        # Build cache from first scan results
        cache = {}
        for f in result1.new_files:
            cache[f.path] = {
                "modified_at": f.modified_at,
                "size_bytes": f.size_bytes,
                "content_hash": f.content_hash,
            }

        # Second scan with cache
        result2 = scan_folder_incremental(
            root_path=str(sample_files),
            category="test",
            cached_files=cache,
            exclude_patterns=["__pycache__"],
            min_size_bytes=1,
        )

        assert len(result2.new_files) == 0
        assert result2.unchanged_count == len(result1.new_files)
        assert result2.removed_count == 0

    def test_detects_modified_file(self, sample_files):
        """Modifying a file should cause it to be re-scanned."""
        # First scan
        result1 = scan_folder_incremental(
            root_path=str(sample_files),
            category="test",
            cached_files={},
            exclude_patterns=["__pycache__"],
            min_size_bytes=1,
        )

        cache = {}
        for f in result1.new_files:
            cache[f.path] = {
                "modified_at": f.modified_at,
                "size_bytes": f.size_bytes,
                "content_hash": f.content_hash,
            }

        # Modify one file (change size to force mismatch)
        report_path = sample_files / "docs" / "report.txt"
        time.sleep(0.1)  # Ensure mtime changes
        report_path.write_text("This is modified content that is longer now!!")

        # Second scan
        result2 = scan_folder_incremental(
            root_path=str(sample_files),
            category="test",
            cached_files=cache,
            exclude_patterns=["__pycache__"],
            min_size_bytes=1,
        )

        assert len(result2.new_files) >= 1
        modified_paths = [f.path for f in result2.new_files]
        assert str(report_path) in modified_paths

    def test_detects_removed_file(self, sample_files):
        """Deleting a file should be detected as removed."""
        # First scan
        result1 = scan_folder_incremental(
            root_path=str(sample_files),
            category="test",
            cached_files={},
            exclude_patterns=["__pycache__"],
            min_size_bytes=1,
        )

        cache = {}
        for f in result1.new_files:
            cache[f.path] = {
                "modified_at": f.modified_at,
                "size_bytes": f.size_bytes,
                "content_hash": f.content_hash,
            }

        # Delete a file
        os.remove(sample_files / "docs" / "notes.csv")

        # Second scan
        result2 = scan_folder_incremental(
            root_path=str(sample_files),
            category="test",
            cached_files=cache,
            exclude_patterns=["__pycache__"],
            min_size_bytes=1,
        )

        assert result2.removed_count == 1

    def test_detects_new_file(self, sample_files):
        """Adding a new file should be detected."""
        # First scan
        result1 = scan_folder_incremental(
            root_path=str(sample_files),
            category="test",
            cached_files={},
            exclude_patterns=["__pycache__"],
            min_size_bytes=1,
        )

        cache = {}
        for f in result1.new_files:
            cache[f.path] = {
                "modified_at": f.modified_at,
                "size_bytes": f.size_bytes,
                "content_hash": f.content_hash,
            }

        # Add a new file
        new_file = sample_files / "docs" / "new_document.txt"
        new_file.write_text("Brand new document content here")

        # Second scan
        result2 = scan_folder_incremental(
            root_path=str(sample_files),
            category="test",
            cached_files=cache,
            exclude_patterns=["__pycache__"],
            min_size_bytes=1,
        )

        assert len(result2.new_files) == 1
        assert result2.new_files[0].name == "new_document.txt"

    def test_category_assigned(self, sample_files):
        """All scanned files should have the given category."""
        result = scan_folder_incremental(
            root_path=str(sample_files),
            category="my-category",
            cached_files={},
            exclude_patterns=["__pycache__"],
            min_size_bytes=1,
        )
        for f in result.new_files:
            assert f.category == "my-category"

    def test_hashes_are_consistent(self, sample_files):
        """Hashing the same file twice should produce the same hash."""
        result1 = scan_folder_incremental(
            root_path=str(sample_files),
            category="test",
            cached_files={},
            exclude_patterns=["__pycache__"],
            min_size_bytes=1,
        )
        result2 = scan_folder_incremental(
            root_path=str(sample_files),
            category="test",
            cached_files={},
            exclude_patterns=["__pycache__"],
            min_size_bytes=1,
        )

        hashes1 = {f.path: f.content_hash for f in result1.new_files}
        hashes2 = {f.path: f.content_hash for f in result2.new_files}

        for path in hashes1:
            assert hashes1[path] == hashes2[path]


# ---------------------------------------------------------------------------
# scan_folder_parallel (legacy wrapper)
# ---------------------------------------------------------------------------

class TestScanFolderParallel:
    """Tests for the legacy scan_folder_parallel wrapper."""

    def test_returns_list_of_fileinfo(self, sample_files):
        files = scan_folder_parallel(
            root_path=str(sample_files),
            category="test",
            exclude_patterns=["__pycache__"],
            min_size_bytes=1,
        )
        assert isinstance(files, list)
        assert len(files) > 0
        for f in files:
            assert isinstance(f, FileInfo)
