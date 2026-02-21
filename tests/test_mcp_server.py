"""
Tests for the MCP server module (src/mcp_server.py).
Tests tool functions with a real database but no MCP framework dependency.
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

from src.scanner import FileInfo
from src.storage import FileDatabase


def make_file_info(
    path="/tmp/test/file.txt",
    name="file.txt",
    extension=".txt",
    size_bytes=1024,
    content_hash="abc123",
    category="test",
    content_text=None,
    tags=None,
):
    return FileInfo(
        path=path,
        name=name,
        extension=extension,
        size_bytes=size_bytes,
        created_at=datetime(2024, 1, 1, 12, 0, 0),
        modified_at=datetime(2024, 1, 1, 12, 0, 0),
        content_hash=content_hash,
        category=category,
        content_text=content_text,
    )


def _setup_db(tmp_path):
    """Create a database with sample files for testing."""
    db = FileDatabase(str(tmp_path / "test.duckdb"))
    files = [
        make_file_info(
            path="/docs/report.pdf", name="report.pdf", extension=".pdf",
            size_bytes=5000000, content_hash="h1", category="documents",
            content_text="Quarterly revenue report Q3 2024",
        ),
        make_file_info(
            path="/code/app.py", name="app.py", extension=".py",
            size_bytes=1500, content_hash="h2", category="development",
            content_text="import flask\napp = Flask(__name__)",
        ),
        make_file_info(
            path="/photos/vacation.jpg", name="vacation.jpg", extension=".jpg",
            size_bytes=3000000, content_hash="h3", category="media",
        ),
        # Duplicate of report.pdf
        make_file_info(
            path="/backup/report_copy.pdf", name="report_copy.pdf", extension=".pdf",
            size_bytes=5000000, content_hash="h1", category="backup",
            content_text="Quarterly revenue report Q3 2024",
        ),
    ]
    for f in files:
        db.insert_file(f)
    # Tag some files
    db.update_tags("/docs/report.pdf", ["finance", "quarterly-report", "pdf-document"])
    db.update_tags("/code/app.py", ["python-script", "development", "web-app"])
    return db


class TestMCPToolFunctions:
    """Test the underlying logic that MCP tools would use."""

    def test_search_finds_files(self, tmp_path):
        db = _setup_db(tmp_path)
        results = db.search("report", limit=10)
        assert len(results) >= 1
        names = [r["name"] for r in results]
        assert "report.pdf" in names
        db.close()

    def test_get_stats(self, tmp_path):
        db = _setup_db(tmp_path)
        stats = db.get_stats()
        assert stats["total_files"] == 4
        assert stats["total_size_bytes"] > 0
        assert stats["duplicate_sets"] == 1
        assert "documents" in stats["by_category"]
        assert ".pdf" in stats["by_extension"]
        db.close()

    def test_find_duplicates(self, tmp_path):
        db = _setup_db(tmp_path)
        duplicates = db.get_duplicates()
        assert len(duplicates) == 1
        assert duplicates[0]["count"] == 2
        assert duplicates[0]["wasted_size"] > 0
        db.close()

    def test_health_metrics(self, tmp_path):
        db = _setup_db(tmp_path)
        metrics = db.get_health_metrics()
        assert metrics["total_files"] == 4
        assert metrics["duplicate_sets"] == 1
        assert metrics["duplicate_files"] > 0
        assert metrics["tagged_files"] == 2
        assert metrics["untagged_files"] == 2
        db.close()

    def test_browse_tags(self, tmp_path):
        db = _setup_db(tmp_path)
        all_tags = db.get_all_tags()
        assert "finance" in all_tags
        assert "python-script" in all_tags
        assert all_tags["finance"] == 1

        # Search by tag
        files = db.get_files_by_tag("finance")
        assert len(files) == 1
        assert files[0]["name"] == "report.pdf"
        db.close()

    def test_run_sql_query(self, tmp_path):
        db = _setup_db(tmp_path)
        results = db.run_query(
            "SELECT name, size_bytes FROM files ORDER BY size_bytes DESC LIMIT 3"
        )
        assert len(results) == 3
        # Largest first
        assert results[0]["size_bytes"] >= results[1]["size_bytes"]
        db.close()

    def test_run_sql_blocks_non_select(self, tmp_path):
        db = _setup_db(tmp_path)
        with pytest.raises(ValueError, match="Only SELECT"):
            db.run_query("DELETE FROM files")
        with pytest.raises(ValueError, match="forbidden keyword"):
            db.run_query("SELECT * FROM files; DROP TABLE files")
        db.close()

    def test_semantic_search_no_embeddings(self, tmp_path):
        db = _setup_db(tmp_path)
        results = db.semantic_search([1.0, 0.0, 0.0])
        assert results == []
        db.close()

    def test_semantic_search_with_embeddings(self, tmp_path):
        db = _setup_db(tmp_path)
        db.store_embedding("/docs/report.pdf", [1.0, 0.0, 0.0], "test")
        db.store_embedding("/code/app.py", [0.0, 1.0, 0.0], "test")

        results = db.semantic_search([0.9, 0.1, 0.0])
        assert len(results) == 2
        assert results[0]["name"] == "report.pdf"
        db.close()


class TestMCPServerCreation:
    """Test MCP server creation without actually starting it."""

    def test_create_server_without_mcp_package(self):
        """If mcp is not installed, create_mcp_server should raise ImportError."""
        import importlib
        import sys

        # Check if mcp is actually installed
        mcp_spec = importlib.util.find_spec("mcp")
        if mcp_spec is not None:
            pytest.skip("mcp package is installed — can't test ImportError path")

        from src.mcp_server import create_mcp_server
        with pytest.raises(ImportError, match="mcp"):
            create_mcp_server()

    def test_get_db_missing_database(self, tmp_path):
        """_get_db should raise FileNotFoundError if DB doesn't exist."""
        from unittest.mock import patch

        with patch("src.mcp_server.load_config") as mock_config:
            mock_config.return_value = {
                "database": {"path": str(tmp_path / "nonexistent.duckdb")},
            }
            from src.mcp_server import _get_db
            with pytest.raises(FileNotFoundError, match="Database not found"):
                _get_db()
