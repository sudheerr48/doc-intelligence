"""
Tests for embedding storage and semantic search (src/core/database.py embeddings + src/ai/).
"""

import json
import math
import os
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

from src.core.models import FileInfo
from src.core.database import FileDatabase


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
    content_text=None,
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


# ---------------------------------------------------------------------------
# Embedding encode/decode
# ---------------------------------------------------------------------------

class TestEmbeddingEncodeDecode:
    def test_roundtrip(self):
        vec = [0.1, 0.2, 0.3, -0.5, 1.0]
        blob = FileDatabase._encode_embedding(vec)
        decoded = FileDatabase._decode_embedding(blob)
        assert len(decoded) == len(vec)
        for a, b in zip(vec, decoded):
            assert abs(a - b) < 1e-6

    def test_empty_vector(self):
        vec = []
        blob = FileDatabase._encode_embedding(vec)
        assert FileDatabase._decode_embedding(blob) == []

    def test_large_vector(self):
        vec = [float(i) / 1000 for i in range(1536)]  # typical embedding size
        blob = FileDatabase._encode_embedding(vec)
        assert len(blob) == 1536 * 4  # 4 bytes per float32
        decoded = FileDatabase._decode_embedding(blob)
        assert len(decoded) == 1536


# ---------------------------------------------------------------------------
# Embedding storage
# ---------------------------------------------------------------------------

class TestEmbeddingStorage:
    def test_store_and_stats(self, tmp_path):
        db = FileDatabase(str(tmp_path / "test.duckdb"))
        db.insert_file(make_file_info(
            path="/a/file.txt", content_text="Hello world", content_hash="h1",
        ))

        vec = [0.1] * 10
        assert db.store_embedding("/a/file.txt", vec, "test-model") is True

        stats = db.get_embedding_stats()
        assert stats["embedded_files"] == 1
        assert stats["files_with_content"] == 1
        db.close()

    def test_store_batch(self, tmp_path):
        db = FileDatabase(str(tmp_path / "test.duckdb"))
        for i in range(3):
            db.insert_file(make_file_info(
                path=f"/f{i}.txt", name=f"f{i}.txt",
                content_text=f"Content {i}", content_hash=f"h{i}",
            ))

        items = [(f"/f{i}.txt", [float(i)] * 5) for i in range(3)]
        count = db.store_embeddings_batch(items, model="test-model")
        assert count == 3

        stats = db.get_embedding_stats()
        assert stats["embedded_files"] == 3
        db.close()

    def test_upsert_overwrites(self, tmp_path):
        db = FileDatabase(str(tmp_path / "test.duckdb"))
        db.insert_file(make_file_info(
            path="/a.txt", content_text="text", content_hash="h1",
        ))

        db.store_embedding("/a.txt", [1.0, 2.0], "model-v1")
        db.store_embedding("/a.txt", [3.0, 4.0], "model-v2")

        stats = db.get_embedding_stats()
        assert stats["embedded_files"] == 1  # not 2
        db.close()


# ---------------------------------------------------------------------------
# Unembedded files
# ---------------------------------------------------------------------------

class TestGetUnembeddedFiles:
    def test_returns_files_with_content_no_embedding(self, tmp_path):
        db = FileDatabase(str(tmp_path / "test.duckdb"))

        # File with content, no embedding
        db.insert_file(make_file_info(
            path="/a.txt", name="a.txt", content_text="has content", content_hash="h1",
        ))
        # File without content
        db.insert_file(make_file_info(
            path="/b.bin", name="b.bin", content_text=None, content_hash="h2",
        ))

        unembedded = db.get_unembedded_files()
        assert len(unembedded) == 1
        assert unembedded[0]["path"] == "/a.txt"
        db.close()

    def test_excludes_already_embedded(self, tmp_path):
        db = FileDatabase(str(tmp_path / "test.duckdb"))

        db.insert_file(make_file_info(
            path="/a.txt", content_text="content", content_hash="h1",
        ))
        db.store_embedding("/a.txt", [0.5] * 5, "model")

        unembedded = db.get_unembedded_files()
        assert len(unembedded) == 0
        db.close()


# ---------------------------------------------------------------------------
# Semantic search (cosine similarity)
# ---------------------------------------------------------------------------

class TestSemanticSearch:
    def _setup_db(self, tmp_path):
        db = FileDatabase(str(tmp_path / "test.duckdb"))

        # Insert 3 files with distinct content
        files = [
            ("/docs/finance.txt", "finance.txt", "Revenue and expense reports", "h1"),
            ("/docs/code.py", "code.py", "Python programming script", "h2"),
            ("/docs/recipe.txt", "recipe.txt", "Chocolate cake recipe", "h3"),
        ]
        for path, name, content, h in files:
            db.insert_file(make_file_info(
                path=path, name=name, content_text=content,
                content_hash=h, extension=name.split(".")[-1],
            ))

        # Store embeddings: orthogonal-ish vectors for easy testing
        db.store_embedding("/docs/finance.txt", [1.0, 0.0, 0.0], "test")
        db.store_embedding("/docs/code.py", [0.0, 1.0, 0.0], "test")
        db.store_embedding("/docs/recipe.txt", [0.0, 0.0, 1.0], "test")

        return db

    def test_finds_most_similar(self, tmp_path):
        db = self._setup_db(tmp_path)

        # Query vector close to "finance"
        results = db.semantic_search([0.9, 0.1, 0.0])
        assert len(results) == 3
        assert results[0]["name"] == "finance.txt"
        assert results[0]["similarity"] > 0.9
        db.close()

    def test_respects_limit(self, tmp_path):
        db = self._setup_db(tmp_path)
        results = db.semantic_search([1.0, 0.0, 0.0], limit=1)
        assert len(results) == 1
        db.close()

    def test_empty_db(self, tmp_path):
        db = FileDatabase(str(tmp_path / "test.duckdb"))
        results = db.semantic_search([1.0, 0.0, 0.0])
        assert results == []
        db.close()

    def test_similarity_scores_are_valid(self, tmp_path):
        db = self._setup_db(tmp_path)
        results = db.semantic_search([0.5, 0.5, 0.0])
        for r in results:
            assert -1.0 <= r["similarity"] <= 1.0
        db.close()

    def test_identical_vector_returns_1(self, tmp_path):
        db = self._setup_db(tmp_path)
        results = db.semantic_search([1.0, 0.0, 0.0])
        assert abs(results[0]["similarity"] - 1.0) < 0.001
        db.close()


# ---------------------------------------------------------------------------
# AI module embedding functions
# ---------------------------------------------------------------------------

class TestGenerateEmbeddings:
    def setup_method(self):
        import src.ai.providers as pmod
        pmod._client = None
        pmod._active_provider = None
        pmod._embedding_client = None
        pmod._embedding_provider = None

    @patch("src.ai.embeddings.get_embedding_client")
    def test_generate_embeddings(self, mock_get_client):
        import src.ai.providers as pmod
        pmod._embedding_provider = "openai"

        mock_client = MagicMock()
        mock_item1 = MagicMock()
        mock_item1.embedding = [0.1, 0.2, 0.3]
        mock_item2 = MagicMock()
        mock_item2.embedding = [0.4, 0.5, 0.6]
        mock_response = MagicMock()
        mock_response.data = [mock_item1, mock_item2]
        mock_client.embeddings.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            from src.ai import generate_embeddings, set_provider
            set_provider("openai")
            result = generate_embeddings(["hello", "world"], model="text-embedding-3-small")

        assert len(result) == 2
        assert result[0] == [0.1, 0.2, 0.3]
        mock_client.embeddings.create.assert_called_once()


class TestIsEmbeddingAvailable:
    def test_no_key(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OPENAI_API_KEY", None)
            os.environ.pop("VOYAGE_API_KEY", None)
            from src.ai import is_embedding_available
            assert is_embedding_available() is False

    def test_with_openai_key(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True):
            os.environ.pop("VOYAGE_API_KEY", None)
            from src.ai import is_embedding_available
            result = is_embedding_available()
            assert isinstance(result, bool)

    def test_with_voyage_key(self):
        with patch.dict(os.environ, {"VOYAGE_API_KEY": "pa-test"}, clear=True):
            os.environ.pop("OPENAI_API_KEY", None)
            with patch.dict("sys.modules", {"voyageai": MagicMock()}):
                from src.ai import is_embedding_available
                assert is_embedding_available() is True
