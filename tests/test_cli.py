"""
CLI smoke tests for scripts and unified CLI entry point.
Verifies that commands run without errors and produce expected output.
"""

import csv
import os
from pathlib import Path
from datetime import datetime

import pytest
from typer.testing import CliRunner

from src.scanner import FileInfo
from src.storage import FileDatabase


runner = CliRunner()


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
        created_at=datetime(2024, 1, 1),
        modified_at=datetime(2024, 1, 1),
        content_hash=content_hash,
        category=category,
    )


def create_test_config(tmp_path, db_path, scan_dir=None):
    """Create a minimal config YAML for testing."""
    config_path = tmp_path / "test_config.yaml"
    scan_path = scan_dir or str(tmp_path / "scan_target")
    config_path.write_text(
        f"database:\n"
        f"  path: {db_path}\n"
        f"scan_folders:\n"
        f"  - path: {scan_path}\n"
        f"    category: test\n"
        f"deduplication:\n"
        f"  hash_algorithm: xxhash\n"
        f"  min_size_bytes: 1\n"
    )
    return str(config_path)


def seed_database(db_path):
    """Insert sample files into a fresh database for testing."""
    db = FileDatabase(db_path)
    files = [
        make_file_info(path="/tmp/a/doc1.pdf", name="doc1.pdf", extension=".pdf",
                       size_bytes=2048, content_hash="hash1", category="docs"),
        make_file_info(path="/tmp/a/doc2.pdf", name="doc2.pdf", extension=".pdf",
                       size_bytes=3072, content_hash="hash2", category="docs"),
        make_file_info(path="/tmp/b/photo.jpg", name="photo.jpg", extension=".jpg",
                       size_bytes=4096, content_hash="hash3", category="images"),
        # Duplicates (same hash)
        make_file_info(path="/tmp/c/dup1.txt", name="dup1.txt", extension=".txt",
                       size_bytes=1024, content_hash="duphash", category="test"),
        make_file_info(path="/tmp/c/dup2.txt", name="dup2.txt", extension=".txt",
                       size_bytes=1024, content_hash="duphash", category="test"),
    ]
    db.insert_batch(files)
    db.close()
    return db_path


# ---------------------------------------------------------------------------
# scripts/scan.py
# ---------------------------------------------------------------------------

class TestScanCLI:
    """Smoke tests for the scan script."""

    def test_scan_help(self):
        from scripts.scan import app
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Scan folders" in result.output

    def test_scan_with_config(self, tmp_path):
        from scripts.scan import app
        scan_dir = tmp_path / "files"
        scan_dir.mkdir()
        (scan_dir / "test.txt").write_text("hello world test content")

        db_path = str(tmp_path / "test.duckdb")
        config_path = create_test_config(tmp_path, db_path, str(scan_dir))

        result = runner.invoke(app, ["--config", config_path])
        assert result.exit_code == 0
        assert "Scan Complete" in result.output

    def test_scan_single_path(self, tmp_path):
        from scripts.scan import app
        scan_dir = tmp_path / "single"
        scan_dir.mkdir()
        (scan_dir / "data.csv").write_text("a,b,c\n1,2,3\n")

        db_path = str(tmp_path / "test.duckdb")
        config_path = create_test_config(tmp_path, db_path)

        result = runner.invoke(app, [
            "--config", config_path,
            "--path", str(scan_dir),
            "--category", "mycat",
        ])
        assert result.exit_code == 0
        assert "Scan Complete" in result.output

    def test_scan_with_algorithm(self, tmp_path):
        from scripts.scan import app
        scan_dir = tmp_path / "algo"
        scan_dir.mkdir()
        (scan_dir / "file.txt").write_text("hash algorithm test content")

        db_path = str(tmp_path / "test.duckdb")
        config_path = create_test_config(tmp_path, db_path, str(scan_dir))

        result = runner.invoke(app, ["--config", config_path, "--algorithm", "sha256"])
        assert result.exit_code == 0
        assert "sha256" in result.output


# ---------------------------------------------------------------------------
# scripts/find_duplicates.py
# ---------------------------------------------------------------------------

class TestDuplicatesCLI:
    """Smoke tests for the find_duplicates script."""

    def test_duplicates_help(self):
        from scripts.find_duplicates import app
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "duplicate" in result.output.lower()

    def test_duplicates_no_db(self, tmp_path):
        from scripts.find_duplicates import app
        db_path = str(tmp_path / "nonexistent.duckdb")
        config_path = create_test_config(tmp_path, db_path)

        result = runner.invoke(app, ["--config", config_path])
        assert result.exit_code == 0
        assert "Database not found" in result.output

    def test_duplicates_with_data(self, tmp_path):
        from scripts.find_duplicates import app
        db_path = str(tmp_path / "test.duckdb")
        seed_database(db_path)
        config_path = create_test_config(tmp_path, db_path)

        result = runner.invoke(app, ["--config", config_path])
        assert result.exit_code == 0
        assert "duplicate" in result.output.lower()

    def test_duplicates_with_limit(self, tmp_path):
        from scripts.find_duplicates import app
        db_path = str(tmp_path / "test.duckdb")
        seed_database(db_path)
        config_path = create_test_config(tmp_path, db_path)

        result = runner.invoke(app, ["--config", config_path, "--limit", "5"])
        assert result.exit_code == 0

    def test_duplicates_with_min_size(self, tmp_path):
        from scripts.find_duplicates import app
        db_path = str(tmp_path / "test.duckdb")
        seed_database(db_path)
        config_path = create_test_config(tmp_path, db_path)

        # Set min_size high enough to filter out duplicates
        result = runner.invoke(app, ["--config", config_path, "--min-size", "999999"])
        assert result.exit_code == 0
        assert "No duplicates found above" in result.output

    def test_duplicates_export_csv(self, tmp_path):
        from scripts.find_duplicates import app
        db_path = str(tmp_path / "test.duckdb")
        seed_database(db_path)
        config_path = create_test_config(tmp_path, db_path)
        csv_path = str(tmp_path / "dups.csv")

        result = runner.invoke(app, ["--config", config_path, "--export-csv", csv_path])
        assert result.exit_code == 0
        assert "Exported" in result.output

        # Verify CSV was created with expected columns
        assert Path(csv_path).exists()
        with open(csv_path) as f:
            reader = csv.reader(f)
            header = next(reader)
            assert "hash" in header
            assert "copies" in header
            assert "paths" in header
            rows = list(reader)
            assert len(rows) >= 1

    def test_duplicates_no_duplicates(self, tmp_path):
        from scripts.find_duplicates import app
        db_path = str(tmp_path / "test.duckdb")
        db = FileDatabase(db_path)
        # Insert files with unique hashes
        db.insert_file(make_file_info(path="/tmp/u1.txt", content_hash="unique1"))
        db.insert_file(make_file_info(path="/tmp/u2.txt", content_hash="unique2"))
        db.close()
        config_path = create_test_config(tmp_path, db_path)

        result = runner.invoke(app, ["--config", config_path])
        assert result.exit_code == 0
        assert "No duplicates found" in result.output


# ---------------------------------------------------------------------------
# scripts/search.py
# ---------------------------------------------------------------------------

class TestSearchCLI:
    """Smoke tests for the search script."""

    def test_search_help(self):
        from scripts.search import app
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Search" in result.output

    def test_search_no_db(self, tmp_path):
        from scripts.search import app
        db_path = str(tmp_path / "nonexistent.duckdb")
        config_path = create_test_config(tmp_path, db_path)

        result = runner.invoke(app, ["test", "--config", config_path])
        assert result.exit_code == 0
        assert "Database not found" in result.output

    def test_search_with_results(self, tmp_path):
        from scripts.search import app
        db_path = str(tmp_path / "test.duckdb")
        seed_database(db_path)
        config_path = create_test_config(tmp_path, db_path)

        result = runner.invoke(app, ["doc", "--config", config_path])
        assert result.exit_code == 0
        assert "doc1.pdf" in result.output

    def test_search_no_results(self, tmp_path):
        from scripts.search import app
        db_path = str(tmp_path / "test.duckdb")
        seed_database(db_path)
        config_path = create_test_config(tmp_path, db_path)

        result = runner.invoke(app, ["zzzznonexistent", "--config", config_path])
        assert result.exit_code == 0
        assert "No files found" in result.output

    def test_search_with_limit(self, tmp_path):
        from scripts.search import app
        db_path = str(tmp_path / "test.duckdb")
        seed_database(db_path)
        config_path = create_test_config(tmp_path, db_path)

        result = runner.invoke(app, ["doc", "--config", config_path, "--limit", "1"])
        assert result.exit_code == 0
        assert "Found" in result.output

    def test_search_with_extension(self, tmp_path):
        from scripts.search import app
        db_path = str(tmp_path / "test.duckdb")
        seed_database(db_path)
        config_path = create_test_config(tmp_path, db_path)

        # Search for photos but filter to .pdf extension -> no match
        result = runner.invoke(app, ["photo", "--config", config_path, "--extension", "pdf"])
        assert result.exit_code == 0
        assert "No files found" in result.output

    def test_search_extension_with_dot(self, tmp_path):
        from scripts.search import app
        db_path = str(tmp_path / "test.duckdb")
        seed_database(db_path)
        config_path = create_test_config(tmp_path, db_path)

        # Extension with leading dot should also work
        result = runner.invoke(app, ["doc", "--config", config_path, "--extension", ".pdf"])
        assert result.exit_code == 0
        assert "doc1.pdf" in result.output


# ---------------------------------------------------------------------------
# scripts/cli.py (unified CLI)
# ---------------------------------------------------------------------------

class TestUnifiedCLI:
    """Smoke tests for the unified CLI entry point."""

    def test_cli_help(self):
        from scripts.cli import app
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "scan" in result.output
        assert "duplicates" in result.output
        assert "search" in result.output
        assert "stats" in result.output

    def test_cli_scan_help(self):
        from scripts.cli import app
        result = runner.invoke(app, ["scan", "--help"])
        assert result.exit_code == 0
        assert "--config" in result.output
        assert "--path" in result.output

    def test_cli_duplicates_help(self):
        from scripts.cli import app
        result = runner.invoke(app, ["duplicates", "--help"])
        assert result.exit_code == 0
        assert "--min-size" in result.output
        assert "--export-csv" in result.output

    def test_cli_search_help(self):
        from scripts.cli import app
        result = runner.invoke(app, ["search", "--help"])
        assert result.exit_code == 0
        assert "--limit" in result.output
        assert "--extension" in result.output

    def test_cli_stats_help(self):
        from scripts.cli import app
        result = runner.invoke(app, ["stats", "--help"])
        assert result.exit_code == 0
        assert "--config" in result.output

    def test_cli_stats_no_db(self, tmp_path):
        from scripts.cli import app
        db_path = str(tmp_path / "nonexistent.duckdb")
        config_path = create_test_config(tmp_path, db_path)

        result = runner.invoke(app, ["stats", "--config", config_path])
        assert result.exit_code == 0
        assert "Database not found" in result.output

    def test_cli_stats_with_data(self, tmp_path):
        from scripts.cli import app
        db_path = str(tmp_path / "test.duckdb")
        seed_database(db_path)
        config_path = create_test_config(tmp_path, db_path)

        result = runner.invoke(app, ["stats", "--config", config_path])
        assert result.exit_code == 0
        assert "Total Files" in result.output
        assert "5" in result.output  # We seeded 5 files

    def test_cli_scan_runs(self, tmp_path):
        from scripts.cli import app
        scan_dir = tmp_path / "files"
        scan_dir.mkdir()
        (scan_dir / "readme.txt").write_text("cli scan integration test")

        db_path = str(tmp_path / "test.duckdb")
        config_path = create_test_config(tmp_path, db_path, str(scan_dir))

        result = runner.invoke(app, ["scan", "--config", config_path])
        assert result.exit_code == 0
        assert "Scan Complete" in result.output

    def test_cli_search_runs(self, tmp_path):
        from scripts.cli import app
        db_path = str(tmp_path / "test.duckdb")
        seed_database(db_path)
        config_path = create_test_config(tmp_path, db_path)

        result = runner.invoke(app, ["search", "doc", "--config", config_path])
        assert result.exit_code == 0
        assert "doc1.pdf" in result.output

    def test_cli_duplicates_runs(self, tmp_path):
        from scripts.cli import app
        db_path = str(tmp_path / "test.duckdb")
        seed_database(db_path)
        config_path = create_test_config(tmp_path, db_path)

        result = runner.invoke(app, ["duplicates", "--config", config_path])
        assert result.exit_code == 0
        assert "duplicate" in result.output.lower()
