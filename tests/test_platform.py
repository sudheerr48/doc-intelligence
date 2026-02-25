"""Tests for cross-platform detection module."""

import pytest
from src.core.platform import detect_platform, PlatformInfo, get_install_instructions


class TestDetectPlatform:
    def test_returns_platform_info(self):
        info = detect_platform()
        assert isinstance(info, PlatformInfo)

    def test_os_is_known(self):
        info = detect_platform()
        assert info.os in ("macOS", "Linux", "Windows")

    def test_has_version(self):
        info = detect_platform()
        assert len(info.os_version) > 0

    def test_has_arch(self):
        info = detect_platform()
        assert info.arch in ("x86_64", "arm64", "aarch64", "AMD64", "x86", "i686")

    def test_has_python_version(self):
        info = detect_platform()
        assert "." in info.python_version  # e.g. "3.11.5"

    def test_has_home_dir(self):
        info = detect_platform()
        assert info.home_dir.exists()

    def test_config_dir_path(self):
        info = detect_platform()
        assert "doc-intelligence" in str(info.config_dir)

    def test_data_dir_path(self):
        info = detect_platform()
        assert "doc-intelligence" in str(info.data_dir) or str(info.data_dir) == str(info.config_dir)

    def test_to_dict(self):
        info = detect_platform()
        d = info.to_dict()
        assert "os" in d
        assert "arch" in d
        assert "python_version" in d
        assert "config_dir" in d


class TestInstallInstructions:
    def test_returns_dict(self):
        instructions = get_install_instructions()
        assert isinstance(instructions, dict)

    def test_has_platform(self):
        instructions = get_install_instructions()
        assert instructions["platform"] in ("macOS", "Linux", "Windows")

    def test_has_package_install(self):
        instructions = get_install_instructions()
        assert "pip install" in instructions["package_install"]

    def test_has_notes(self):
        instructions = get_install_instructions()
        assert isinstance(instructions["notes"], list)
        assert len(instructions["notes"]) >= 1
