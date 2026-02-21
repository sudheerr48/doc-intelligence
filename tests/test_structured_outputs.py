"""
Tests for structured output via tool_use / function calling in src/ai.py.
Tests the _chat_with_tool function and its integration with classify/nl_to_sql/health.
"""

import json
import os
from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# _chat_with_tool tests
# ---------------------------------------------------------------------------

class TestChatWithTool:
    def setup_method(self):
        import src.ai as ai_mod
        ai_mod._client = None
        ai_mod._active_provider = None

    @patch("src.ai._get_client")
    def test_anthropic_tool_use(self, mock_get_client):
        """Test that Anthropic provider uses tool_use correctly."""
        mock_client = MagicMock()
        mock_block = MagicMock()
        mock_block.type = "tool_use"
        mock_block.input = {"tags": ["python-script", "development"]}
        mock_response = MagicMock()
        mock_response.content = [mock_block]
        mock_client.messages.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        from src.ai import _chat_with_tool, set_provider
        set_provider("anthropic")

        result = _chat_with_tool(
            system="You are a classifier",
            user_msg="Classify this file",
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            tool_name="classify_file",
            tool_description="Classify a file",
            tool_schema={
                "type": "object",
                "properties": {
                    "tags": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["tags"],
            },
        )

        assert result == {"tags": ["python-script", "development"]}
        # Verify the API was called with tool_choice
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["tool_choice"] == {"type": "tool", "name": "classify_file"}
        assert len(call_kwargs["tools"]) == 1
        assert call_kwargs["tools"][0]["name"] == "classify_file"

    @patch("src.ai._get_client")
    def test_openai_function_calling(self, mock_get_client):
        """Test that OpenAI provider uses function calling correctly."""
        mock_client = MagicMock()
        mock_tool_call = MagicMock()
        mock_tool_call.function.arguments = json.dumps({"sql": "SELECT * FROM files LIMIT 10"})
        mock_choice = MagicMock()
        mock_choice.message.tool_calls = [mock_tool_call]
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        from src.ai import _chat_with_tool, set_provider
        set_provider("openai")

        result = _chat_with_tool(
            system="You are a SQL generator",
            user_msg="show all files",
            model="gpt-4o",
            max_tokens=500,
            tool_name="generate_sql",
            tool_description="Generate SQL",
            tool_schema={
                "type": "object",
                "properties": {"sql": {"type": "string"}},
                "required": ["sql"],
            },
        )

        assert result == {"sql": "SELECT * FROM files LIMIT 10"}
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["tool_choice"]["type"] == "function"
        assert call_kwargs["tools"][0]["type"] == "function"


# ---------------------------------------------------------------------------
# classify_file with structured output
# ---------------------------------------------------------------------------

class TestClassifyFileStructured:
    def setup_method(self):
        import src.ai as ai_mod
        ai_mod._client = None
        ai_mod._active_provider = None

    @patch("src.ai._chat_with_tool")
    def test_uses_tool_use_primary(self, mock_tool):
        """classify_file should use _chat_with_tool as primary path."""
        mock_tool.return_value = {"tags": ["python-script", "development", "source-code"]}

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}):
            from src.ai import classify_file
            tags = classify_file(
                name="app.py", extension=".py",
                path="/home/user/app.py", size_bytes=1024,
            )
        assert tags == ["python-script", "development", "source-code"]
        mock_tool.assert_called_once()

    @patch("src.ai._chat_with_tool", side_effect=Exception("tool_use failed"))
    @patch("src.ai._chat")
    def test_falls_back_to_plain_chat(self, mock_chat, mock_tool):
        """classify_file should fall back to _chat if tool_use fails."""
        mock_chat.return_value = '["fallback-tag", "development"]'

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}):
            from src.ai import classify_file
            tags = classify_file(
                name="app.py", extension=".py",
                path="/home/user/app.py", size_bytes=1024,
            )
        assert "fallback-tag" in tags
        mock_tool.assert_called_once()
        mock_chat.assert_called_once()

    @patch("src.ai._chat_with_tool")
    def test_lowercases_and_limits_tags(self, mock_tool):
        mock_tool.return_value = {"tags": ["UPPER", "Mixed", "a", "b", "c", "d", "e"]}

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}):
            from src.ai import classify_file
            tags = classify_file(
                name="f.txt", extension=".txt",
                path="/f.txt", size_bytes=100,
            )
        assert all(t == t.lower() for t in tags)
        assert len(tags) <= 5


# ---------------------------------------------------------------------------
# classify_batch with structured output
# ---------------------------------------------------------------------------

class TestClassifyBatchStructured:
    def setup_method(self):
        import src.ai as ai_mod
        ai_mod._client = None
        ai_mod._active_provider = None

    @patch("src.ai._chat_with_tool")
    def test_uses_tool_use(self, mock_tool):
        mock_tool.return_value = {
            "classifications": {
                "1": ["python-script", "dev"],
                "2": ["photo", "media"],
            }
        }

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}):
            from src.ai import classify_batch
            files = [
                {"path": "/a.py", "name": "a.py", "extension": ".py",
                 "size_bytes": 1000, "content_text": None},
                {"path": "/b.jpg", "name": "b.jpg", "extension": ".jpg",
                 "size_bytes": 5000, "content_text": None},
            ]
            result = classify_batch(files, batch_size=10)

        assert "/a.py" in result
        assert "/b.jpg" in result
        assert "python-script" in result["/a.py"]
        assert "photo" in result["/b.jpg"]


# ---------------------------------------------------------------------------
# nl_to_sql with structured output
# ---------------------------------------------------------------------------

class TestNlToSqlStructured:
    def setup_method(self):
        import src.ai as ai_mod
        ai_mod._client = None
        ai_mod._active_provider = None

    @patch("src.ai._chat_with_tool")
    def test_uses_tool_use(self, mock_tool):
        expected = "SELECT name, size_bytes FROM files WHERE extension = '.pdf' ORDER BY size_bytes DESC LIMIT 100"
        mock_tool.return_value = {"sql": expected}

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}):
            from src.ai import nl_to_sql
            sql = nl_to_sql("show me the largest PDF files")

        assert sql == expected
        mock_tool.assert_called_once()

    @patch("src.ai._chat_with_tool", side_effect=Exception("fail"))
    @patch("src.ai._chat")
    def test_falls_back_to_plain_chat(self, mock_chat, mock_tool):
        expected = "SELECT * FROM files LIMIT 10"
        mock_chat.return_value = expected

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}):
            from src.ai import nl_to_sql
            sql = nl_to_sql("show all files")

        assert sql == expected


# ---------------------------------------------------------------------------
# generate_health_insights with structured output
# ---------------------------------------------------------------------------

class TestHealthInsightsStructured:
    def setup_method(self):
        import src.ai as ai_mod
        ai_mod._client = None
        ai_mod._active_provider = None

    @patch("src.ai._chat_with_tool")
    def test_uses_tool_use(self, mock_tool):
        expected = {
            "score": 85,
            "grade": "B",
            "summary": "Your file system is in good shape.",
            "issues": [{"severity": "low", "title": "Some stale files", "detail": "50 old files."}],
            "recommendations": ["Archive old files."],
        }
        mock_tool.return_value = expected

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}):
            from src.ai import generate_health_insights
            result = generate_health_insights({"total_files": 500})

        assert result["score"] == 85
        assert result["grade"] == "B"
        mock_tool.assert_called_once()

    @patch("src.ai._chat_with_tool", side_effect=Exception("fail"))
    @patch("src.ai._chat")
    def test_fallback_with_valid_json(self, mock_chat, mock_tool):
        expected = {
            "score": 72,
            "grade": "C",
            "summary": "Moderate issues.",
            "issues": [],
            "recommendations": ["Clean up."],
        }
        mock_chat.return_value = json.dumps(expected)

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}):
            from src.ai import generate_health_insights
            result = generate_health_insights({"total_files": 100})

        assert result["score"] == 72

    @patch("src.ai._chat_with_tool", side_effect=Exception("fail"))
    @patch("src.ai._chat")
    def test_fallback_with_invalid_json(self, mock_chat, mock_tool):
        mock_chat.return_value = "I couldn't analyze your files properly."

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}):
            from src.ai import generate_health_insights
            result = generate_health_insights({"total_files": 100})

        assert result["score"] == 0
        assert result["grade"] == "?"
        assert len(result["recommendations"]) == 1


# ---------------------------------------------------------------------------
# Tool schemas validation
# ---------------------------------------------------------------------------

class TestToolSchemas:
    def test_classify_tool_schema_has_required_fields(self):
        from src.ai import _CLASSIFY_TOOL_SCHEMA
        assert "tags" in _CLASSIFY_TOOL_SCHEMA["properties"]
        assert "tags" in _CLASSIFY_TOOL_SCHEMA["required"]

    def test_classify_batch_tool_schema(self):
        from src.ai import _CLASSIFY_BATCH_TOOL_SCHEMA
        assert "classifications" in _CLASSIFY_BATCH_TOOL_SCHEMA["properties"]
        assert "classifications" in _CLASSIFY_BATCH_TOOL_SCHEMA["required"]

    def test_sql_tool_schema(self):
        from src.ai import _SQL_TOOL_SCHEMA
        assert "sql" in _SQL_TOOL_SCHEMA["properties"]
        assert _SQL_TOOL_SCHEMA["properties"]["sql"]["type"] == "string"

    def test_health_tool_schema(self):
        from src.ai import _HEALTH_TOOL_SCHEMA
        required = _HEALTH_TOOL_SCHEMA["required"]
        assert "score" in required
        assert "grade" in required
        assert "summary" in required
        assert "issues" in required
        assert "recommendations" in required
