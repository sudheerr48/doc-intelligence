"""Tests for the HTML report generator."""

import pytest
from pathlib import Path
from datetime import datetime

from src.storage import FileDatabase
from src.scanner import FileInfo


@pytest.fixture
def report_db(db_path):
    """Create a database with data for report testing."""
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
            ("doc1.pdf", ".pdf", 5_000_000, "hash_a", "documents"),
            ("doc2.pdf", ".pdf", 3_000_000, "hash_b", "documents"),
            ("photo.jpg", ".jpg", 8_000_000, "hash_c", "images"),
            ("dup1.txt", ".txt", 1_000, "hash_dup", "documents"),
            ("dup2.txt", ".txt", 1_000, "hash_dup", "documents"),
            ("data.csv", ".csv", 2_000_000, "hash_d", "data"),
        ]
    ]
    db.insert_batch(files)
    return db


class TestHTMLReport:
    def test_generate_html_report(self, report_db, db_path):
        """Generates valid HTML with expected sections."""
        from scripts.report import generate_html_report

        config = {"database": {"path": db_path}}
        html = generate_html_report(config)

        assert "<!DOCTYPE html>" in html
        assert "Doc Intelligence Report" in html
        assert "chart.js" in html.lower() or "Chart" in html

    def test_report_contains_stats(self, report_db, db_path):
        """Report includes file counts and sizes."""
        from scripts.report import generate_html_report

        config = {"database": {"path": db_path}}
        html = generate_html_report(config)

        # Should show total files (6)
        assert "6" in html

    def test_report_contains_extensions(self, report_db, db_path):
        """Report includes extension breakdown."""
        from scripts.report import generate_html_report

        config = {"database": {"path": db_path}}
        html = generate_html_report(config)

        assert ".pdf" in html
        assert ".jpg" in html

    def test_report_contains_duplicates(self, report_db, db_path):
        """Report includes duplicate information."""
        from scripts.report import generate_html_report

        config = {"database": {"path": db_path}}
        html = generate_html_report(config)

        # Should mention duplicate group
        assert "dup" in html.lower()

    def test_report_contains_big_files(self, report_db, db_path):
        """Report includes largest files."""
        from scripts.report import generate_html_report

        config = {"database": {"path": db_path}}
        html = generate_html_report(config)

        assert "photo.jpg" in html

    def test_run_report_saves_file(self, report_db, db_path, tmp_path):
        """run_report saves HTML to disk."""
        from scripts.report import run_report

        output = str(tmp_path / "test_report.html")
        config = {"database": {"path": db_path}}
        run_report(config=config, output_path=output)

        assert Path(output).exists()
        content = Path(output).read_text()
        assert "<!DOCTYPE html>" in content

    def test_run_report_no_db(self, tmp_path):
        """Handles missing database gracefully."""
        from scripts.report import run_report

        config = {"database": {"path": str(tmp_path / "nonexistent.duckdb")}}
        # Should not raise
        run_report(config=config, output_path=str(tmp_path / "report.html"))

    def test_html_escape(self):
        """HTML escaping works correctly."""
        from scripts.report import _html_escape

        assert _html_escape("<script>") == "&lt;script&gt;"
        assert _html_escape('a"b') == "a&quot;b"
        assert _html_escape("a&b") == "a&amp;b"


class TestReportCLI:
    def test_help(self):
        """CLI help works."""
        from typer.testing import CliRunner
        from scripts.report import app

        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "html" in result.output.lower() or "report" in result.output.lower()
