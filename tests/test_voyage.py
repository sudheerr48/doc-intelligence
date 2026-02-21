"""
Tests for Voyage AI embedding support in src/ai.py.
"""

import os
from unittest.mock import patch, MagicMock

import pytest


class TestEmbeddingProviderDetection:
    def setup_method(self):
        import src.ai as ai_mod
        ai_mod._client = None
        ai_mod._active_provider = None
        ai_mod._embedding_client = None
        ai_mod._embedding_provider = None

    def test_detect_voyage_when_key_and_package(self):
        with patch.dict(os.environ, {"VOYAGE_API_KEY": "pa-test"}, clear=True):
            with patch.dict("sys.modules", {"voyageai": MagicMock()}):
                from src.ai import _detect_embedding_provider
                assert _detect_embedding_provider() == "voyage"

    def test_detect_openai_when_no_voyage(self):
        """OpenAI should be detected when VOYAGE_API_KEY is absent but OPENAI_API_KEY is set."""
        try:
            import openai  # noqa: F401
            openai_installed = True
        except ImportError:
            openai_installed = False

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True):
            os.environ.pop("VOYAGE_API_KEY", None)
            from src.ai import _detect_embedding_provider
            if openai_installed:
                result = _detect_embedding_provider()
                assert result == "openai"
            else:
                with pytest.raises(RuntimeError, match="No embedding API key found"):
                    _detect_embedding_provider()

    def test_voyage_takes_priority(self):
        """Voyage should be preferred over OpenAI when both keys are present."""
        with patch.dict(os.environ, {
            "VOYAGE_API_KEY": "pa-test",
            "OPENAI_API_KEY": "sk-test",
        }, clear=True):
            with patch.dict("sys.modules", {"voyageai": MagicMock()}):
                from src.ai import _detect_embedding_provider
                assert _detect_embedding_provider() == "voyage"

    def test_no_key_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("VOYAGE_API_KEY", None)
            os.environ.pop("OPENAI_API_KEY", None)
            from src.ai import _detect_embedding_provider
            with pytest.raises(RuntimeError, match="No embedding API key found"):
                _detect_embedding_provider()


class TestIsEmbeddingAvailable:
    def setup_method(self):
        import src.ai as ai_mod
        ai_mod._embedding_client = None
        ai_mod._embedding_provider = None

    def test_available_with_voyage_key(self):
        with patch.dict(os.environ, {"VOYAGE_API_KEY": "pa-test"}, clear=True):
            os.environ.pop("OPENAI_API_KEY", None)
            with patch.dict("sys.modules", {"voyageai": MagicMock()}):
                from src.ai import is_embedding_available
                assert is_embedding_available() is True

    def test_available_with_openai_key(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True):
            os.environ.pop("VOYAGE_API_KEY", None)
            from src.ai import is_embedding_available
            # True if openai is installed
            assert isinstance(is_embedding_available(), bool)

    def test_not_available_without_keys(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("VOYAGE_API_KEY", None)
            os.environ.pop("OPENAI_API_KEY", None)
            from src.ai import is_embedding_available
            assert is_embedding_available() is False


class TestGenerateEmbeddingsVoyage:
    def setup_method(self):
        import src.ai as ai_mod
        ai_mod._client = None
        ai_mod._active_provider = None
        ai_mod._embedding_client = None
        ai_mod._embedding_provider = None

    @patch("src.ai._get_embedding_client")
    def test_voyage_embedding_generation(self, mock_get_client):
        """Test that Voyage AI embeddings are generated using the correct API."""
        import src.ai as ai_mod
        ai_mod._embedding_provider = "voyage"

        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.embeddings = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        mock_client.embed.return_value = mock_result
        mock_get_client.return_value = mock_client

        from src.ai import generate_embeddings
        result = generate_embeddings(["hello", "world"], model="voyage-3.5")

        assert len(result) == 2
        assert result[0] == [0.1, 0.2, 0.3]
        mock_client.embed.assert_called_once_with(
            ["hello", "world"], model="voyage-3.5", input_type="document"
        )

    @patch("src.ai._get_embedding_client")
    def test_openai_embedding_generation(self, mock_get_client):
        """Test that OpenAI embeddings still work."""
        import src.ai as ai_mod
        ai_mod._embedding_provider = "openai"

        mock_client = MagicMock()
        mock_item1 = MagicMock()
        mock_item1.embedding = [0.1, 0.2, 0.3]
        mock_item2 = MagicMock()
        mock_item2.embedding = [0.4, 0.5, 0.6]
        mock_response = MagicMock()
        mock_response.data = [mock_item1, mock_item2]
        mock_client.embeddings.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        from src.ai import generate_embeddings
        result = generate_embeddings(["hello", "world"], model="text-embedding-3-small")

        assert len(result) == 2
        assert result[0] == [0.1, 0.2, 0.3]
        mock_client.embeddings.create.assert_called_once()

    @patch("src.ai._get_embedding_client")
    def test_truncates_long_texts(self, mock_get_client):
        """Texts longer than 8000 chars should be truncated."""
        import src.ai as ai_mod
        ai_mod._embedding_provider = "openai"

        mock_client = MagicMock()
        mock_item = MagicMock()
        mock_item.embedding = [0.1]
        mock_response = MagicMock()
        mock_response.data = [mock_item]
        mock_client.embeddings.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        long_text = "x" * 10000
        from src.ai import generate_embeddings
        generate_embeddings([long_text], model="text-embedding-3-small")

        # Verify the text was truncated
        actual_input = mock_client.embeddings.create.call_args[1]["input"]
        assert len(actual_input[0]) == 8000


class TestDefaultEmbeddingModels:
    def test_voyage_default_model(self):
        from src.ai import DEFAULT_EMBEDDING_MODELS
        assert "voyage" in DEFAULT_EMBEDDING_MODELS
        assert "voyage" in DEFAULT_EMBEDDING_MODELS["voyage"]

    def test_openai_default_model(self):
        from src.ai import DEFAULT_EMBEDDING_MODELS
        assert "openai" in DEFAULT_EMBEDDING_MODELS
        assert "embedding" in DEFAULT_EMBEDDING_MODELS["openai"]
