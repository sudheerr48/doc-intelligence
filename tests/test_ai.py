"""
Tests for the AI module.
Tests parsing logic directly. API calls are mocked.
"""

import json
import os
from unittest.mock import patch, MagicMock

import pytest

from src.ai.classification import _parse_tags, _parse_batch_tags
from src.ai.providers import is_ai_available


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
            os.environ.pop("ANTHROPIC_API_KEY", None)
            os.environ.pop("OPENAI_API_KEY", None)
            assert is_ai_available() is False

    def test_with_anthropic_key(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
            result = is_ai_available()
            assert isinstance(result, bool)

    def test_with_openai_key(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            result = is_ai_available()
            assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# Provider detection tests
# ---------------------------------------------------------------------------

class TestProviderDetection:
    def setup_method(self):
        import src.ai.providers as pmod
        pmod._client = None
        pmod._active_provider = None

    def test_detect_anthropic(self):
        from src.ai.providers import _detect_provider
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}, clear=True):
            assert _detect_provider() == "anthropic"

    def test_detect_openai(self):
        from src.ai.providers import _detect_provider
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            assert _detect_provider() == "openai"

    def test_anthropic_takes_priority(self):
        from src.ai.providers import _detect_provider
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant", "OPENAI_API_KEY": "sk-oai"}, clear=True):
            assert _detect_provider() == "anthropic"

    def test_no_key_raises(self):
        from src.ai.providers import _detect_provider
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            os.environ.pop("OPENAI_API_KEY", None)
            with pytest.raises(RuntimeError, match="No AI API key found"):
                _detect_provider()

    def test_set_provider_valid(self):
        from src.ai.providers import set_provider, get_provider
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True):
            set_provider("openai")
            assert get_provider() == "openai"

    def test_set_provider_invalid(self):
        from src.ai.providers import set_provider
        with pytest.raises(ValueError, match="Unknown provider"):
            set_provider("invalid")

    def test_default_model_anthropic(self):
        from src.ai.providers import default_model, set_provider, DEFAULT_MODELS
        set_provider("anthropic")
        assert default_model() == DEFAULT_MODELS["anthropic"]
        assert default_model("custom-model") == "custom-model"

    def test_default_model_openai(self):
        from src.ai.providers import default_model, set_provider, DEFAULT_MODELS
        set_provider("openai")
        assert default_model() == DEFAULT_MODELS["openai"]


# ---------------------------------------------------------------------------
# classify_file mock test
# ---------------------------------------------------------------------------

class TestClassifyFile:
    def setup_method(self):
        import src.ai.providers as pmod
        pmod._client = None
        pmod._active_provider = None

    @patch("src.ai.classification.chat_with_tool", side_effect=Exception("no real API"))
    @patch("src.ai.classification.chat")
    def test_classify_returns_tags_fallback(self, mock_chat, mock_tool):
        mock_chat.return_value = '["python-script", "development"]'

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}):
            from src.ai.classification import classify_file
            tags = classify_file(
                name="app.py",
                extension=".py",
                path="/home/user/app.py",
                size_bytes=1024,
            )
        assert tags == ["python-script", "development"]
        mock_chat.assert_called_once()

    @patch("src.ai.classification.chat_with_tool", side_effect=Exception("no real API"))
    @patch("src.ai.classification.chat")
    def test_classify_with_content_fallback(self, mock_chat, mock_tool):
        mock_chat.return_value = '["tax-return", "finance", "pdf-document"]'

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}):
            from src.ai.classification import classify_file
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
    def setup_method(self):
        import src.ai.providers as pmod
        pmod._client = None
        pmod._active_provider = None

    @patch("src.ai.classification.chat_with_tool", side_effect=Exception("no real API"))
    @patch("src.ai.classification.chat")
    def test_batch_classify_fallback(self, mock_chat, mock_tool):
        mock_chat.return_value = '{"1": ["python-script", "dev"], "2": ["photo", "media"]}'

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}):
            from src.ai.classification import classify_batch
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
    def setup_method(self):
        import src.ai.providers as pmod
        pmod._client = None
        pmod._active_provider = None

    @patch("src.ai.query.chat_with_tool", side_effect=Exception("no real API"))
    @patch("src.ai.query.chat")
    def test_nl_to_sql_simple_fallback(self, mock_chat, mock_tool):
        expected_sql = "SELECT name, size_bytes FROM files WHERE extension = '.pdf' ORDER BY size_bytes DESC LIMIT 100"
        mock_chat.return_value = expected_sql

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}):
            from src.ai.query import nl_to_sql
            sql = nl_to_sql("show me the largest PDF files")
        assert "SELECT" in sql
        assert ".pdf" in sql.lower() or "pdf" in sql.lower()

    @patch("src.ai.query.chat_with_tool", side_effect=Exception("no real API"))
    @patch("src.ai.query.chat")
    def test_nl_to_sql_strips_code_fences_fallback(self, mock_chat, mock_tool):
        mock_chat.return_value = "```sql\nSELECT * FROM files LIMIT 10\n```"

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}):
            from src.ai.query import nl_to_sql
            sql = nl_to_sql("show all files")
        assert not sql.startswith("```")
        assert "SELECT" in sql


# ---------------------------------------------------------------------------
# Health insights mock test
# ---------------------------------------------------------------------------

class TestGenerateHealthInsights:
    def setup_method(self):
        import src.ai.providers as pmod
        pmod._client = None
        pmod._active_provider = None

    @patch("src.ai.insights.chat_with_tool", side_effect=Exception("no real API"))
    @patch("src.ai.insights.chat")
    def test_generate_insights_fallback(self, mock_chat, mock_tool):
        insight = {
            "score": 72,
            "grade": "C",
            "summary": "Your file system has moderate issues.",
            "issues": [{"severity": "medium", "title": "Duplicates", "detail": "Found many."}],
            "recommendations": ["Clean up duplicates."],
        }
        mock_chat.return_value = json.dumps(insight)

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}):
            from src.ai.insights import generate_health_insights
            result = generate_health_insights({"total_files": 1000})
        assert result["score"] == 72
        assert result["grade"] == "C"
        assert len(result["issues"]) == 1


# ---------------------------------------------------------------------------
# OpenAI-specific mock tests
# ---------------------------------------------------------------------------

class TestOpenAIProvider:
    def setup_method(self):
        import src.ai.providers as pmod
        pmod._client = None
        pmod._active_provider = None

    @patch("src.ai.classification.chat_with_tool", side_effect=Exception("no real API"))
    @patch("src.ai.classification.chat")
    def test_classify_with_openai_fallback(self, mock_chat, mock_tool):
        mock_chat.return_value = '["spreadsheet", "finance", "quarterly-report"]'

        from src.ai.providers import set_provider
        from src.ai.classification import classify_file
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            set_provider("openai")
            tags = classify_file(
                name="q3_report.xlsx",
                extension=".xlsx",
                path="/home/user/Reports/q3_report.xlsx",
                size_bytes=25000,
            )
        assert "finance" in tags
        assert "spreadsheet" in tags
        mock_chat.assert_called_once()

    @patch("src.ai.query.chat_with_tool", side_effect=Exception("no real API"))
    @patch("src.ai.query.chat")
    def test_nl_query_with_openai_fallback(self, mock_chat, mock_tool):
        expected_sql = "SELECT name, size_bytes FROM files ORDER BY size_bytes DESC LIMIT 10"
        mock_chat.return_value = expected_sql

        from src.ai.providers import set_provider
        from src.ai.query import nl_to_sql
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            set_provider("openai")
            sql = nl_to_sql("top 10 largest files")
        assert "SELECT" in sql
        assert "ORDER BY size_bytes DESC" in sql
