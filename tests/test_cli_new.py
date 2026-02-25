"""
Tests for new CLI commands: tag, ask, health, tags.
Uses typer.testing.CliRunner for smoke testing.
"""

import json
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest
from typer.testing import CliRunner

from scripts.cli import app
from src.core.database import FileDatabase
from src.core.models import FileInfo


runner = CliRunner()


@pytest.fixture
def populated_db(tmp_path):
    """Create a config and database with sample data."""
    db_path = tmp_path / "data" / "files.duckdb"
    db_path.parent.mkdir(parents=True)

    config_content = f"""
scan_folders:
  - path: {tmp_path}
    category: test

include_extensions: []
exclude_patterns: []

deduplication:
  hash_algorithm: xxhash
  min_size_bytes: 0

database:
  path: {db_path}

staging:
  path: {tmp_path / '_TO_DELETE'}

reports:
  output_dir: {tmp_path / 'reports'}

ai:
  model: claude-sonnet-4-20250514
  batch_size: 20
  max_tag_files: 100
"""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config_content)

    db = FileDatabase(str(db_path))
    files = [
        FileInfo(
            path=str(tmp_path / "report.pdf"),
            name="report.pdf", extension=".pdf",
            size_bytes=50000,
            created_at=datetime(2024, 1, 1),
            modified_at=datetime(2024, 6, 1),
            content_hash="abc123", category="test",
            content_text="Financial report Q2",
        ),
        FileInfo(
            path=str(tmp_path / "app.py"),
            name="app.py", extension=".py",
            size_bytes=3000,
            created_at=datetime(2024, 3, 1),
            modified_at=datetime(2024, 7, 1),
            content_hash="def456", category="test",
            content_text="import flask",
        ),
    ]
    db.insert_batch(files)
    db.close()

    return config_path, db_path


# ---------------------------------------------------------------------------
# Health command
# ---------------------------------------------------------------------------

class TestHealthCommand:
    def test_health_basic(self, populated_db):
        config_path, _ = populated_db
        result = runner.invoke(app, ["health", "-c", str(config_path)])
        assert result.exit_code == 0
        assert "Health Score" in result.output or "HEALTH REPORT" in result.output

    def test_health_json_output(self, populated_db):
        config_path, _ = populated_db
        result = runner.invoke(app, ["health", "-c", str(config_path), "--json"])
        assert result.exit_code == 0
        # Should be parseable JSON
        data = json.loads(result.output)
        assert "metrics" in data
        assert "health" in data

    def test_health_no_db(self, tmp_path):
        config_content = f"""
scan_folders: []
include_extensions: []
exclude_patterns: []
deduplication:
  hash_algorithm: xxhash
  min_size_bytes: 0
database:
  path: {tmp_path / 'nonexistent.duckdb'}
staging:
  path: {tmp_path / '_TO_DELETE'}
reports:
  output_dir: {tmp_path}
"""
        config_path = tmp_path / "config.yaml"
        config_path.write_text(config_content)

        result = runner.invoke(app, ["health", "-c", str(config_path)])
        assert "not found" in result.output.lower() or result.exit_code == 0


# ---------------------------------------------------------------------------
# Tags command
# ---------------------------------------------------------------------------

class TestTagsCommand:
    def test_tags_no_tags(self, populated_db):
        config_path, _ = populated_db
        result = runner.invoke(app, ["tags", "-c", str(config_path)])
        assert result.exit_code == 0
        assert "No tags" in result.output or "tag" in result.output.lower()

    def test_tags_with_data(self, populated_db):
        config_path, db_path = populated_db
        # Add some tags first
        db = FileDatabase(str(db_path))
        db.update_tags(str(populated_db[0].parent / "report.pdf"), ["finance", "report"])
        db.close()

        result = runner.invoke(app, ["tags", "-c", str(config_path)])
        assert result.exit_code == 0
        assert "finance" in result.output

    def test_tags_filter_by_name(self, populated_db):
        config_path, db_path = populated_db
        db = FileDatabase(str(db_path))
        db.update_tags(str(populated_db[0].parent / "report.pdf"), ["finance", "report"])
        db.close()

        result = runner.invoke(app, ["tags", "-c", str(config_path), "finance"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Tag command (AI classify) — mocked
# ---------------------------------------------------------------------------

class TestTagCommand:
    @patch("src.ai.is_ai_available", return_value=False)
    def test_tag_no_api_key(self, mock_avail, populated_db):
        config_path, _ = populated_db
        result = runner.invoke(app, ["tag", "-c", str(config_path)])
        assert result.exit_code == 0
        # Free tier blocks AI tagging before API key check
        assert "Pro" in result.output or "ANTHROPIC_API_KEY" in result.output


# ---------------------------------------------------------------------------
# Ask command — mocked
# ---------------------------------------------------------------------------

class TestAskCommand:
    @patch("src.ai.is_ai_available", return_value=False)
    def test_ask_no_api_key(self, mock_avail, populated_db):
        config_path, _ = populated_db
        result = runner.invoke(app, ["ask", "show all files", "-c", str(config_path)])
        assert result.exit_code == 0
        # Free tier blocks AI features before API key check
        assert "Pro" in result.output or "ANTHROPIC_API_KEY" in result.output
