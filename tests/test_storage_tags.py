"""
Tests for tag-related storage methods and new query capabilities.
"""

import json
from datetime import datetime

import pytest

from src.storage import FileDatabase
from src.scanner import FileInfo


@pytest.fixture
def db(tmp_path):
    """Create a database with sample files."""
    db_path = str(tmp_path / "test.duckdb")
    database = FileDatabase(db_path)

    files = [
        FileInfo(
            path="/home/user/docs/report.pdf",
            name="report.pdf",
            extension=".pdf",
            size_bytes=50000,
            created_at=datetime(2024, 1, 1),
            modified_at=datetime(2024, 6, 15),
            content_hash="abc123",
            category="documents",
            content_text="Quarterly financial report Q2 2024",
        ),
        FileInfo(
            path="/home/user/code/app.py",
            name="app.py",
            extension=".py",
            size_bytes=3000,
            created_at=datetime(2024, 3, 1),
            modified_at=datetime(2024, 7, 20),
            content_hash="def456",
            category="code",
            content_text="import flask\napp = Flask(__name__)",
        ),
        FileInfo(
            path="/home/user/photos/vacation.jpg",
            name="vacation.jpg",
            extension=".jpg",
            size_bytes=5000000,
            created_at=datetime(2023, 8, 1),
            modified_at=datetime(2023, 8, 1),
            content_hash="ghi789",
            category="photos",
            content_text=None,
        ),
        FileInfo(
            path="/home/user/docs/report_copy.pdf",
            name="report_copy.pdf",
            extension=".pdf",
            size_bytes=50000,
            created_at=datetime(2024, 2, 1),
            modified_at=datetime(2024, 6, 15),
            content_hash="abc123",  # same hash = duplicate
            category="documents",
            content_text="Quarterly financial report Q2 2024",
        ),
    ]
    database.insert_batch(files)
    yield database
    database.close()


# ---------------------------------------------------------------------------
# Tag operations
# ---------------------------------------------------------------------------

class TestUpdateTags:
    def test_update_tags(self, db):
        result = db.update_tags("/home/user/docs/report.pdf", ["finance", "quarterly-report"])
        assert result is True

        # Verify stored
        row = db.conn.execute(
            "SELECT tags FROM files WHERE path = ?",
            ["/home/user/docs/report.pdf"]
        ).fetchone()
        assert row is not None
        tags = json.loads(row[0])
        assert tags == ["finance", "quarterly-report"]

    def test_update_tags_nonexistent_file(self, db):
        # Should succeed (UPDATE affects 0 rows, no error)
        result = db.update_tags("/nonexistent/file.txt", ["tag1"])
        assert result is True

    def test_batch_update_tags(self, db):
        tag_map = {
            "/home/user/docs/report.pdf": ["finance", "pdf-document"],
            "/home/user/code/app.py": ["python-script", "development"],
        }
        count = db.batch_update_tags(tag_map)
        assert count == 2


class TestGetAllTags:
    def test_no_tags(self, db):
        tags = db.get_all_tags()
        assert tags == {}

    def test_with_tags(self, db):
        db.update_tags("/home/user/docs/report.pdf", ["finance", "report"])
        db.update_tags("/home/user/code/app.py", ["development", "python"])
        db.update_tags("/home/user/photos/vacation.jpg", ["photo", "personal"])

        tags = db.get_all_tags()
        assert "finance" in tags
        assert "development" in tags
        assert "photo" in tags
        assert tags["finance"] == 1

    def test_tag_counts(self, db):
        db.update_tags("/home/user/docs/report.pdf", ["finance"])
        db.update_tags("/home/user/docs/report_copy.pdf", ["finance"])
        db.update_tags("/home/user/code/app.py", ["development"])

        tags = db.get_all_tags()
        assert tags["finance"] == 2
        assert tags["development"] == 1


class TestGetFilesByTag:
    def test_get_files_by_tag(self, db):
        db.update_tags("/home/user/docs/report.pdf", ["finance", "report"])
        db.update_tags("/home/user/code/app.py", ["development"])

        files = db.get_files_by_tag("finance")
        assert len(files) == 1
        assert files[0]["name"] == "report.pdf"
        assert "finance" in files[0]["tags"]

    def test_no_matching_tag(self, db):
        files = db.get_files_by_tag("nonexistent-tag")
        assert files == []


class TestGetUntaggedFiles:
    def test_all_untagged(self, db):
        untagged = db.get_untagged_files()
        assert len(untagged) == 4

    def test_some_tagged(self, db):
        db.update_tags("/home/user/docs/report.pdf", ["finance"])
        db.update_tags("/home/user/code/app.py", ["dev"])

        untagged = db.get_untagged_files()
        assert len(untagged) == 2

    def test_limit(self, db):
        untagged = db.get_untagged_files(limit=2)
        assert len(untagged) == 2


# ---------------------------------------------------------------------------
# run_query
# ---------------------------------------------------------------------------

class TestRunQuery:
    def test_select_all(self, db):
        results = db.run_query("SELECT name, size_bytes FROM files ORDER BY name")
        assert len(results) == 4
        assert results[0]["name"] == "app.py"

    def test_select_with_filter(self, db):
        results = db.run_query("SELECT name FROM files WHERE extension = '.pdf'")
        assert len(results) == 2

    def test_aggregation(self, db):
        results = db.run_query("SELECT COUNT(*) as total FROM files")
        assert results[0]["total"] == 4

    def test_rejects_delete(self, db):
        with pytest.raises(ValueError, match="Only SELECT"):
            db.run_query("DELETE FROM files WHERE path = '/test'")

    def test_rejects_drop(self, db):
        with pytest.raises(ValueError, match="Only SELECT"):
            db.run_query("DROP TABLE files")

    def test_rejects_insert(self, db):
        with pytest.raises(ValueError, match="Only SELECT"):
            db.run_query("INSERT INTO files (path) VALUES ('/test')")

    def test_rejects_update(self, db):
        with pytest.raises(ValueError, match="Only SELECT"):
            db.run_query("UPDATE files SET name = 'hacked'")

    def test_rejects_non_select(self, db):
        with pytest.raises(ValueError, match="Only SELECT"):
            db.run_query("EXPLAIN SELECT * FROM files")

    def test_rejects_select_with_embedded_drop(self, db):
        with pytest.raises(ValueError, match="forbidden keyword"):
            db.run_query("SELECT * FROM files; DROP TABLE files")

    def test_invalid_sql(self, db):
        with pytest.raises(RuntimeError, match="Query execution failed"):
            db.run_query("SELECT nonexistent_column FROM files")


# ---------------------------------------------------------------------------
# get_health_metrics
# ---------------------------------------------------------------------------

class TestGetHealthMetrics:
    def test_returns_expected_keys(self, db):
        metrics = db.get_health_metrics()

        expected_keys = [
            "total_files", "total_size", "duplicate_sets", "duplicate_files",
            "wasted_by_duplicates", "stale_files", "stale_size",
            "large_files", "large_size", "top_large_files",
            "new_files_7d", "new_size_7d", "extension_types",
            "category_breakdown", "top_duplicates",
            "tagged_files", "untagged_files", "by_extension",
        ]
        for key in expected_keys:
            assert key in metrics, f"Missing key: {key}"

    def test_correct_totals(self, db):
        metrics = db.get_health_metrics()
        assert metrics["total_files"] == 4
        assert metrics["total_size"] > 0

    def test_detects_duplicates(self, db):
        metrics = db.get_health_metrics()
        assert metrics["duplicate_sets"] == 1  # abc123 has 2 files

    def test_tagged_count(self, db):
        db.update_tags("/home/user/docs/report.pdf", ["finance"])
        metrics = db.get_health_metrics()
        assert metrics["tagged_files"] == 1
        assert metrics["untagged_files"] == 3

    def test_category_breakdown(self, db):
        metrics = db.get_health_metrics()
        categories = [c["category"] for c in metrics["category_breakdown"]]
        assert "documents" in categories
        assert "code" in categories


# ---------------------------------------------------------------------------
# Schema migration (tags column)
# ---------------------------------------------------------------------------

class TestSchemaMigration:
    def test_tags_column_exists(self, db):
        columns = {
            row[0] for row in
            db.conn.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'files'"
            ).fetchall()
        }
        assert "tags" in columns
