"""
Shared test fixtures for doc-intelligence tests.
Creates temp directories with known small files for deterministic testing.
"""

import os
import shutil
import tempfile
from pathlib import Path
from datetime import datetime

import pytest


@pytest.fixture
def temp_dir(tmp_path):
    """Provide a clean temporary directory."""
    return tmp_path


@pytest.fixture
def sample_files(tmp_path):
    """
    Create a directory tree with known files for scanner testing.

    Structure:
        sample_files/
        ├── docs/
        │   ├── report.txt      (26 bytes, known content)
        │   ├── notes.csv       (45 bytes, known content)
        │   └── readme.md       (21 bytes, known content)
        ├── images/
        │   ├── photo.jpg       (16 bytes, fake binary)
        │   └── icon.png        (14 bytes, fake binary)
        ├── code/
        │   ├── app.py          (22 bytes)
        │   └── __pycache__/
        │       └── app.cpython-39.pyc  (should be excluded)
        ├── empty.txt           (0 bytes, should be skipped by min_size)
        └── tiny.txt            (5 bytes, near min_size threshold)
    """
    root = tmp_path / "sample_files"
    root.mkdir()

    # docs/
    docs = root / "docs"
    docs.mkdir()
    (docs / "report.txt").write_text("This is a test report file")
    (docs / "notes.csv").write_text("name,value\nalpha,1\nbeta,2\ngamma,3\n")
    (docs / "readme.md").write_text("# Doc Intelligence Test")

    # images/ (fake binary content)
    images = root / "images"
    images.mkdir()
    (images / "photo.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 12)
    (images / "icon.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 6)

    # code/ with __pycache__ (should be excluded)
    code = root / "code"
    code.mkdir()
    (code / "app.py").write_text("print('hello world')\n")
    pycache = code / "__pycache__"
    pycache.mkdir()
    (pycache / "app.cpython-39.pyc").write_bytes(b"\x00" * 50)

    # Edge cases at root level
    (root / "empty.txt").write_text("")
    (root / "tiny.txt").write_text("hello")

    return root


@pytest.fixture
def duplicate_files(tmp_path):
    """
    Create files with known duplicate content for dedup testing.

    Structure:
        duplicates/
        ├── original.txt    (same content as copy1 and copy2)
        ├── copy1.txt       (same content as original)
        ├── copy2.txt       (same content as original)
        ├── unique1.txt     (unique content)
        └── unique2.txt     (unique content)
    """
    root = tmp_path / "duplicates"
    root.mkdir()

    dup_content = "This is duplicate content for testing purposes.\n" * 10
    (root / "original.txt").write_text(dup_content)
    (root / "copy1.txt").write_text(dup_content)
    (root / "copy2.txt").write_text(dup_content)

    (root / "unique1.txt").write_text("Unique content number one\n" * 5)
    (root / "unique2.txt").write_text("Unique content number two\n" * 5)

    return root


@pytest.fixture
def db_path(tmp_path):
    """Provide a temporary database path."""
    return str(tmp_path / "test.duckdb")
