"""
Tests for .env file support (python-dotenv integration).
"""

import os
from pathlib import Path

import pytest


class TestDotenvLoading:
    """Verify python-dotenv is importable and loads .env files."""

    def test_dotenv_importable(self):
        from dotenv import load_dotenv
        assert callable(load_dotenv)

    def test_loads_env_file(self, tmp_path, monkeypatch):
        """Create a .env file and verify load_dotenv picks it up."""
        from dotenv import load_dotenv

        env_file = tmp_path / ".env"
        env_file.write_text("DOC_INTEL_TEST_VAR=hello_from_dotenv\n")

        # Ensure it's not already set
        monkeypatch.delenv("DOC_INTEL_TEST_VAR", raising=False)
        assert os.environ.get("DOC_INTEL_TEST_VAR") is None

        load_dotenv(str(env_file))
        assert os.environ.get("DOC_INTEL_TEST_VAR") == "hello_from_dotenv"

        # Clean up
        monkeypatch.delenv("DOC_INTEL_TEST_VAR", raising=False)

    def test_env_example_exists(self):
        """Verify .env.example ships with the project."""
        project_root = Path(__file__).parent.parent
        env_example = project_root / ".env.example"
        assert env_example.exists(), ".env.example should exist at project root"
        content = env_example.read_text()
        assert "ANTHROPIC_API_KEY" in content
        assert "OPENAI_API_KEY" in content
