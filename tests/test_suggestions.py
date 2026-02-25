"""Tests for smart suggestions module."""

import pytest
from unittest.mock import MagicMock
from src.ai.suggestions import (
    suggest_organization,
    _suggest_tag_groups,
    _suggest_old_downloads,
    _suggest_large_file_cleanup,
    _fmt_size,
)


class TestFmtSize:
    def test_bytes(self):
        assert "B" in _fmt_size(500)

    def test_kilobytes(self):
        assert "KB" in _fmt_size(5000)

    def test_megabytes(self):
        assert "MB" in _fmt_size(5_000_000)

    def test_gigabytes(self):
        assert "GB" in _fmt_size(5_000_000_000)


class TestSuggestTagGroups:
    def test_returns_empty_for_no_tags(self):
        db = MagicMock()
        db.get_all_tags.return_value = {}
        result = _suggest_tag_groups(db)
        assert result == []

    def test_returns_empty_for_low_count_tags(self):
        db = MagicMock()
        db.get_all_tags.return_value = {"misc": 2}
        result = _suggest_tag_groups(db)
        assert result == []

    def test_suggests_for_scattered_tagged_files(self):
        db = MagicMock()
        db.get_all_tags.return_value = {"finance": 10}
        db.get_files_by_tag.return_value = [
            {"path": f"/dir{i}/file{j}.pdf", "name": f"file{j}.pdf"}
            for i in range(5) for j in range(2)
        ]
        result = _suggest_tag_groups(db)
        assert len(result) >= 1
        assert result[0]["type"] == "tag_group"
        assert result[0]["tag"] == "finance"


class TestSuggestOldDownloads:
    def test_returns_empty_when_few_old_files(self):
        db = MagicMock()
        db.conn.execute.return_value.fetchall.return_value = [
            ("/dl/a.zip", "a.zip", 1000, "2024-01-01")
        ]
        result = _suggest_old_downloads(db)
        assert result == []

    def test_returns_suggestion_for_many_old_downloads(self):
        db = MagicMock()
        db.conn.execute.return_value.fetchall.return_value = [
            (f"/dl/file{i}.zip", f"file{i}.zip", 50000, "2024-01-01")
            for i in range(10)
        ]
        result = _suggest_old_downloads(db)
        assert len(result) == 1
        assert result[0]["type"] == "old_downloads"
        assert result[0]["priority"] == "high"


class TestSuggestLargeFiles:
    def test_returns_empty_when_no_large_files(self):
        db = MagicMock()
        db.conn.execute.return_value.fetchall.return_value = []
        result = _suggest_large_file_cleanup(db)
        assert result == []

    def test_returns_suggestion_for_large_files(self):
        db = MagicMock()
        db.conn.execute.return_value.fetchall.return_value = [
            (f"/big/file{i}.iso", f"file{i}.iso", 500_000_000, ".iso", "downloads")
            for i in range(3)
        ]
        result = _suggest_large_file_cleanup(db)
        assert len(result) == 1
        assert result[0]["type"] == "large_files"


class TestSuggestOrganization:
    def test_returns_list(self):
        db = MagicMock()
        db.get_all_tags.return_value = {}
        db.conn.execute.return_value.fetchall.return_value = []
        result = suggest_organization(db)
        assert isinstance(result, list)

    def test_respects_max_suggestions(self):
        db = MagicMock()
        db.get_all_tags.return_value = {}
        db.conn.execute.return_value.fetchall.return_value = []
        result = suggest_organization(db, max_suggestions=3)
        assert len(result) <= 3
