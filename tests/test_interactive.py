"""Tests for the interactive mode."""

import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

from src.core.database import FileDatabase
from src.core.models import FileInfo


@pytest.fixture
def interactive_db(db_path):
    """Create a database with data for interactive testing."""
    db = FileDatabase(db_path)
    files = [
        FileInfo(
            path=f"/test/{name}",
            name=name,
            extension=ext,
            size_bytes=size,
            created_at=datetime.now(),
            modified_at=datetime.now(),
            content_hash=h,
            category="test",
        )
        for name, ext, size, h in [
            ("file1.txt", ".txt", 1000, "hash_a"),
            ("file2.txt", ".txt", 2000, "hash_b"),
            ("dup1.pdf", ".pdf", 5000, "hash_dup"),
            ("dup2.pdf", ".pdf", 5000, "hash_dup"),
        ]
    ]
    db.insert_batch(files)
    return db


class TestPrintSavings:
    def test_no_duplicates(self):
        """No duplicates shows clean message."""
        from src.interactive import _print_savings
        # Should not raise
        _print_savings([])

    def test_with_duplicates(self):
        """Shows savings summary for duplicates."""
        from src.interactive import _print_savings

        duplicates = [
            {"count": 2, "total_size": 10000, "wasted_size": 5000, "paths": ["/a", "/b"]},
        ]
        # Should not raise
        _print_savings(duplicates)


class TestGetDb:
    def test_returns_none_when_missing(self, tmp_path):
        """Returns None when database doesn't exist."""
        from src.interactive import _get_db

        config = {"database": {"path": str(tmp_path / "nonexistent.duckdb")}}
        assert _get_db(config) is None

    def test_returns_db_when_exists(self, interactive_db, db_path):
        """Returns FileDatabase when database exists."""
        from src.interactive import _get_db

        config = {"database": {"path": db_path}}
        db = _get_db(config)
        assert db is not None
        db.close()


class TestInteractiveModule:
    def test_module_imports(self):
        """Module imports without error."""
        from src.interactive import run_interactive
        assert callable(run_interactive)

    def test_interactive_stats(self, interactive_db, db_path):
        """Stats function works with populated DB."""
        from src.interactive import _interactive_stats

        config = {"database": {"path": db_path}}
        # Should not raise
        _interactive_stats(config)
        interactive_db.close()

    def test_interactive_search_import(self):
        """Search flow is importable."""
        from src.interactive import _interactive_search
        assert callable(_interactive_search)
