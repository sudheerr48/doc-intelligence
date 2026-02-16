"""Tests for the Streamlit dashboard module."""

import pytest
from pathlib import Path
from datetime import datetime

streamlit = pytest.importorskip("streamlit", reason="Streamlit not installed")

from src.storage import FileDatabase
from src.scanner import FileInfo


@pytest.fixture
def dashboard_db(db_path):
    """Create a database with data for dashboard testing."""
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
            category=cat,
        )
        for name, ext, size, h, cat in [
            ("doc1.pdf", ".pdf", 5_000_000, "h1", "documents"),
            ("doc2.pdf", ".pdf", 3_000_000, "h2", "documents"),
            ("photo.jpg", ".jpg", 8_000_000, "h3", "images"),
            ("dup1.txt", ".txt", 1_000, "h_dup", "misc"),
            ("dup2.txt", ".txt", 1_000, "h_dup", "misc"),
        ]
    ]
    db.insert_batch(files)
    return db


class TestDashboardHelpers:
    def test_format_size_short(self):
        """Format size helper works."""
        from scripts.dashboard import format_size_short

        assert format_size_short(0) == "0.0 B"
        assert "KB" in format_size_short(1024)
        assert "MB" in format_size_short(1_048_576)

    def test_format_size_short_none(self):
        """Handles None input."""
        from scripts.dashboard import format_size_short

        assert format_size_short(None) == "0 B"

    def test_get_db(self, dashboard_db, db_path):
        """get_db returns a working database."""
        from scripts.dashboard import get_db

        config = {"database": {"path": db_path}}
        db = get_db(config)
        stats = db.get_stats()
        assert stats["total_files"] == 5
        db.close()


class TestDashboardModule:
    def test_module_imports(self):
        """Dashboard module imports without error."""
        import scripts.dashboard
        assert hasattr(scripts.dashboard, "main_dashboard")

    def test_dashboard_function_exists(self):
        """main_dashboard function is callable."""
        from scripts.dashboard import main_dashboard
        assert callable(main_dashboard)
