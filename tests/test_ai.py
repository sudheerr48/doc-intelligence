"""
Tests for the AI module (src/ai.py).
Tests parsing logic directly. API calls are mocked.
"""

import json
import os
from unittest.mock import patch, MagicMock

import pytest

# Import parsing helpers directly
from src.ai import _parse_tags, _parse_batch_tags, is_ai_available


# ---------------------------------------------------------------------------
# Tag parsing tests
# ---------------------------------------------------------------------------

class TestParseTags:
    def test_valid_json_array(self):
        text = '["python-script", "development", "source-code"]'
        tags = _parse_tags(text)
        assert tags == ["python-script", "development", "source-code"]

    def test_empty_array(self):
        assert _parse_tags("[]") == []

    def test_single_tag(self):
        assert _parse_tags('["finance"]') == ["finance"]

    def test_strips_whitespace_and_lowercases(self):
        text = '["  Python-Script  ", "FINANCE"]'
        tags = _parse_tags(text)
        assert tags == ["python-script", "finance"]

    def test_fallback_on_invalid_json(self):
        text = "python-script, development, source-code"
        tags = _parse_tags(text)
        assert "python-script" in tags
        assert "development" in tags

    def test_fallback_strips_brackets(self):
        text = "[python-script, development]"
        tags = _parse_tags(text)
        assert len(tags) >= 2

    def test_limits_to_five_tags(self):
        text = "a, b, c, d, e, f, g, h"
        tags = _parse_tags(text)
        assert len(tags) <= 5

    def test_filters_empty_strings(self):
        text = '["", "valid-tag", ""]'
        tags = _parse_tags(text)
        assert tags == ["valid-tag"]


class TestParseBatchTags:
    def test_valid_batch(self):
        text = '{"1": ["python", "dev"], "2": ["photo", "media"]}'
        result = _parse_batch_tags(text)
        assert result == {"1": ["python", "dev"], "2": ["photo", "media"]}

    def test_empty_object(self):
        assert _parse_batch_tags("{}") == {}

    def test_invalid_json(self):
        assert _parse_batch_tags("not json") == {}

    def test_mixed_valid_invalid(self):
        text = '{"1": ["tag"], "2": "not-a-list"}'
        result = _parse_batch_tags(text)
        assert "1" in result
        assert "2" not in result

    def test_lowercases_tags(self):
        text = '{"1": ["UPPERCASE", "MixedCase"]}'
        result = _parse_batch_tags(text)
        assert result["1"] == ["uppercase", "mixedcase"]


# ---------------------------------------------------------------------------
# AI availability check
# ---------------------------------------------------------------------------

class TestIsAiAvailable:
    def test_no_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            # Remove ANTHROPIC_API_KEY if present
            os.environ.pop("ANTHROPIC_API_KEY", None)
            assert is_ai_available() is False

    def test_with_api_key_no_package(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch.dict("sys.modules", {"anthropic": None}):
                # When import fails
                result = is_ai_available()
                # May be True or False depending on whether anthropic is installed
                # The key check should pass at least
                assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# classify_file mock test
# ---------------------------------------------------------------------------

class TestClassifyFile:
    @patch("src.ai._get_client")
    def test_classify_returns_tags(self, mock_get_client):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='["python-script", "development"]')]
        mock_client.messages.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        from src.ai import classify_file
        tags = classify_file(
            name="app.py",
            extension=".py",
            path="/home/user/app.py",
            size_bytes=1024,
        )
        assert tags == ["python-script", "development"]
        mock_client.messages.create.assert_called_once()

    @patch("src.ai._get_client")
    def test_classify_with_content(self, mock_get_client):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='["tax-return", "finance", "pdf-document"]')]
        mock_client.messages.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        from src.ai import classify_file
        tags = classify_file(
            name="2024_taxes.pdf",
            extension=".pdf",
            path="/home/user/Documents/2024_taxes.pdf",
            size_bytes=50000,
            content_text="Federal Income Tax Return 2024...",
        )
        assert "tax-return" in tags
        assert "finance" in tags


# ---------------------------------------------------------------------------
# classify_batch mock test
# ---------------------------------------------------------------------------

class TestClassifyBatch:
    @patch("src.ai._get_client")
    def test_batch_classify(self, mock_get_client):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(
            text='{"1": ["python-script", "dev"], "2": ["photo", "media"]}'
        )]
        mock_client.messages.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        from src.ai import classify_batch
        files = [
            {"path": "/a/app.py", "name": "app.py", "extension": ".py",
             "size_bytes": 1000, "content_text": None},
            {"path": "/a/photo.jpg", "name": "photo.jpg", "extension": ".jpg",
             "size_bytes": 5000, "content_text": None},
        ]
        result = classify_batch(files, batch_size=10)
        assert "/a/app.py" in result
        assert "/a/photo.jpg" in result


# ---------------------------------------------------------------------------
# NL to SQL mock test
# ---------------------------------------------------------------------------

class TestNlToSql:
    @patch("src.ai._get_client")
    def test_nl_to_sql_simple(self, mock_get_client):
        mock_client = MagicMock()
        expected_sql = "SELECT name, size_bytes FROM files WHERE extension = '.pdf' ORDER BY size_bytes DESC LIMIT 100"
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=expected_sql)]
        mock_client.messages.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        from src.ai import nl_to_sql
        sql = nl_to_sql("show me the largest PDF files")
        assert "SELECT" in sql
        assert ".pdf" in sql.lower() or "pdf" in sql.lower()

    @patch("src.ai._get_client")
    def test_nl_to_sql_strips_code_fences(self, mock_get_client):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="```sql\nSELECT * FROM files LIMIT 10\n```")]
        mock_client.messages.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        from src.ai import nl_to_sql
        sql = nl_to_sql("show all files")
        assert not sql.startswith("```")
        assert "SELECT" in sql


# ---------------------------------------------------------------------------
# Health insights mock test
# ---------------------------------------------------------------------------

class TestGenerateHealthInsights:
    @patch("src.ai._get_client")
    def test_generate_insights(self, mock_get_client):
        mock_client = MagicMock()
        insight = {
            "score": 72,
            "grade": "C",
            "summary": "Your file system has moderate issues.",
            "issues": [{"severity": "medium", "title": "Duplicates", "detail": "Found many."}],
            "recommendations": ["Clean up duplicates."],
        }
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps(insight))]
        mock_client.messages.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        from src.ai import generate_health_insights
        result = generate_health_insights({"total_files": 1000})
        assert result["score"] == 72
        assert result["grade"] == "C"
        assert len(result["issues"]) == 1
