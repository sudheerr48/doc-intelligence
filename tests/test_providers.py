"""Tests for the provider plugin system."""

import pytest


class TestRegistry:
    """Test provider registry operations."""

    def test_builtin_providers_registered(self):
        from src.providers.registry import list_all
        all_providers = list_all()
        assert "builtin" in all_providers["extractor"]
        assert "builtin" in all_providers["embedding"]
        assert "builtin" in all_providers["llm"]
        assert "builtin" in all_providers["classifier"]
        assert "builtin" in all_providers["vectorstore"]

    def test_register_custom_provider(self):
        from src.providers.registry import register, get_provider, list_providers

        class MyExtractor:
            def extract(self, file_path):
                return "test"
            def supported_extensions(self):
                return {".test"}

        register("extractor", "test-custom", MyExtractor)
        assert "test-custom" in list_providers("extractor")

        cls = get_provider("extractor", "test-custom")
        assert cls is MyExtractor

    def test_register_invalid_component_type(self):
        from src.providers.registry import register
        with pytest.raises(ValueError, match="Unknown component type"):
            register("invalid-type", "foo", object)

    def test_get_unknown_provider(self):
        from src.providers.registry import get_provider
        with pytest.raises(KeyError, match="No 'nonexistent' provider"):
            get_provider("extractor", "nonexistent")

    def test_list_providers(self):
        from src.providers.registry import list_providers
        providers = list_providers("extractor")
        assert isinstance(providers, list)
        assert "builtin" in providers

    def test_list_all(self):
        from src.providers.registry import list_all
        all_p = list_all()
        assert set(all_p.keys()) == {"extractor", "embedding", "llm", "classifier", "vectorstore"}


class TestInterfaces:
    """Test Protocol interface checking."""

    def test_builtin_extractor_conforms(self):
        from src.providers.interfaces import TextExtractor
        from src.providers.builtin_extractor import BuiltinExtractor
        ext = BuiltinExtractor()
        assert isinstance(ext, TextExtractor)

    def test_builtin_embedding_conforms(self):
        from src.providers.interfaces import EmbeddingProvider
        from src.providers.builtin_embedding import BuiltinEmbedding
        emb = BuiltinEmbedding()
        assert isinstance(emb, EmbeddingProvider)

    def test_builtin_llm_conforms(self):
        from src.providers.interfaces import LLMProvider
        from src.providers.builtin_llm import BuiltinLLM
        # Don't instantiate (needs API key), just check the class has methods
        assert hasattr(BuiltinLLM, "chat")
        assert hasattr(BuiltinLLM, "chat_structured")
        assert hasattr(BuiltinLLM, "is_available")

    def test_builtin_classifier_conforms(self):
        from src.providers.interfaces import FileClassifier
        from src.providers.builtin_classifier import BuiltinClassifier
        cls = BuiltinClassifier()
        assert isinstance(cls, FileClassifier)

    def test_builtin_vectorstore_conforms(self):
        from src.providers.interfaces import VectorStore
        from src.providers.builtin_vectorstore import BuiltinVectorStore
        # Needs a db instance, just check methods exist
        assert hasattr(BuiltinVectorStore, "store")
        assert hasattr(BuiltinVectorStore, "search")
        assert hasattr(BuiltinVectorStore, "stats")


class TestFactory:
    """Test provider factory."""

    def test_create_providers_defaults(self):
        from src.providers.factory import create_providers
        config = {"providers": {}}
        providers = create_providers(config)
        assert providers.extractor is not None
        assert providers.embedding is not None
        assert providers.llm is not None
        assert providers.classifier is not None
        # vectorstore is None without a db (lazy init)
        assert providers.vectorstore is None

    def test_create_providers_no_providers_key(self):
        from src.providers.factory import create_providers
        config = {}
        providers = create_providers(config)
        assert providers.extractor is not None

    def test_create_providers_with_override(self):
        from src.providers.factory import create_providers
        from src.providers.registry import register

        class FakeExtractor:
            def __init__(self): pass
            def extract(self, fp): return "fake"
            def supported_extensions(self): return set()

        register("extractor", "fake", FakeExtractor)
        config = {}
        providers = create_providers(config, overrides={"extractor": "fake"})
        assert providers.extractor.extract("any") == "fake"

    def test_extractor_extract(self, tmp_path):
        from src.providers.factory import create_providers

        # Create a test file
        test_file = tmp_path / "hello.txt"
        test_file.write_text("Hello world from test file")

        config = {}
        providers = create_providers(config)
        text = providers.extractor.extract(str(test_file))
        assert text is not None
        assert "Hello world" in text
