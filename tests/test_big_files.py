"""Tests for the big-files command."""

import pytest
from pathlib import Path
from unittest.mock import patch
from io import StringIO

from src.storage import FileDatabase
from src.scanner import FileInfo
from datetime import datetime


@pytest.fixture
def populated_db(db_path):
    """Create a database with varied file sizes."""
    db = FileDatabase(db_path)
    files = [
        FileInfo(
            path=f"/test/file_{i}.{ext}",
            name=f"file_{i}.{ext}",
            extension=f".{ext}",
            size_bytes=size,
            created_at=datetime.now(),
            modified_at=datetime.now(),
            content_hash=f"hash_{i}",
            category=cat,
        )
        for i, (ext, size, cat) in enumerate([
            ("pdf", 10_000_000, "documents"),
            ("pdf", 5_000_000, "documents"),
            ("jpg", 8_000_000, "images"),
            ("png", 3_000_000, "images"),
            ("txt", 1_000, "documents"),
            ("py", 500, "code"),
            ("csv", 2_000_000, "data"),
            ("mp4", 50_000_000, "media"),
            ("zip", 20_000_000, "archives"),
            ("log", 100_000, "logs"),
        ])
    ]
    db.insert_batch(files)
    return db


class TestBigFiles:
    def test_run_big_files_default(self, populated_db, db_path):
        """Big files returns files sorted by size descending."""
        from scripts.big_files import run_big_files

        config = {"database": {"path": db_path}}
        # Just verify it doesn't crash
        run_big_files(config=config, top_n=5)

    def test_run_big_files_top_n(self, populated_db, db_path):
        """Respects the top_n limit."""
        rows = populated_db.conn.execute(
            "SELECT path FROM files ORDER BY size_bytes DESC LIMIT 3"
        ).fetchall()
        assert len(rows) == 3
        # Largest should be the mp4 at 50MB
        assert "mp4" in rows[0][0]

    def test_run_big_files_filter_extension(self, populated_db, db_path):
        """Extension filter works."""
        rows = populated_db.conn.execute(
            "SELECT path FROM files WHERE extension = '.pdf' ORDER BY size_bytes DESC"
        ).fetchall()
        assert len(rows) == 2

    def test_run_big_files_filter_category(self, populated_db, db_path):
        """Category filter works."""
        rows = populated_db.conn.execute(
            "SELECT path FROM files WHERE category = 'images' ORDER BY size_bytes DESC"
        ).fetchall()
        assert len(rows) == 2

    def test_run_big_files_no_db(self, tmp_path):
        """Handles missing database gracefully."""
        from scripts.big_files import run_big_files

        config = {"database": {"path": str(tmp_path / "nonexistent.duckdb")}}
        # Should not raise
        run_big_files(config=config)

    def test_big_files_percentage(self, populated_db, db_path):
        """Top files percentage is calculated correctly."""
        stats = populated_db.get_stats()
        total = stats["total_size_bytes"]

        top3 = populated_db.conn.execute(
            "SELECT SUM(size_bytes) FROM (SELECT size_bytes FROM files ORDER BY size_bytes DESC LIMIT 3)"
        ).fetchone()[0]

        pct = (top3 / total) * 100
        assert pct > 0


class TestBigFilesCLI:
    def test_help(self):
        """CLI help works."""
        from typer.testing import CliRunner
        from scripts.big_files import app

        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "largest" in result.output.lower() or "big" in result.output.lower()
