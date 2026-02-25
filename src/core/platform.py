"""
Cross-platform detection and OS-specific utilities.

Provides:
  - OS detection with version info
  - Default paths per platform (config, data, cache)
  - Platform-specific feature availability
  - Install/integration hints per OS
"""

import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class PlatformInfo:
    """Current platform information."""
    os: str              # "macOS", "Windows", "Linux"
    os_version: str      # e.g. "14.2", "11", "6.5.0"
    arch: str            # "arm64", "x86_64"
    python_version: str
    home_dir: Path
    config_dir: Path
    data_dir: Path
    cache_dir: Path

    def to_dict(self) -> dict:
        return {
            "os": self.os,
            "os_version": self.os_version,
            "arch": self.arch,
            "python_version": self.python_version,
            "home_dir": str(self.home_dir),
            "config_dir": str(self.config_dir),
            "data_dir": str(self.data_dir),
            "cache_dir": str(self.cache_dir),
        }


def detect_platform() -> PlatformInfo:
    """Detect the current platform and return structured info."""
    system = platform.system()
    home = Path.home()

    if system == "Darwin":
        os_name = "macOS"
        os_version = platform.mac_ver()[0] or platform.release()
        config_dir = home / "Library" / "Application Support" / "doc-intelligence"
        data_dir = config_dir
        cache_dir = home / "Library" / "Caches" / "doc-intelligence"
    elif system == "Windows":
        os_name = "Windows"
        os_version = platform.version()
        appdata = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        config_dir = appdata / "doc-intelligence"
        data_dir = config_dir
        cache_dir = Path(
            os.environ.get("LOCALAPPDATA", home / "AppData" / "Local")
        ) / "doc-intelligence" / "cache"
    else:
        os_name = "Linux"
        os_version = platform.release()
        config_dir = Path(
            os.environ.get("XDG_CONFIG_HOME", home / ".config")
        ) / "doc-intelligence"
        data_dir = Path(
            os.environ.get("XDG_DATA_HOME", home / ".local" / "share")
        ) / "doc-intelligence"
        cache_dir = Path(
            os.environ.get("XDG_CACHE_HOME", home / ".cache")
        ) / "doc-intelligence"

    return PlatformInfo(
        os=os_name,
        os_version=os_version,
        arch=platform.machine(),
        python_version=platform.python_version(),
        home_dir=home,
        config_dir=config_dir,
        data_dir=data_dir,
        cache_dir=cache_dir,
    )


def get_default_scan_folders() -> list[dict]:
    """Return OS-appropriate default folders to scan."""
    info = detect_platform()
    home = info.home_dir

    base = [
        {"path": str(home / "Documents"), "category": "documents"},
        {"path": str(home / "Downloads"), "category": "downloads"},
        {"path": str(home / "Desktop"), "category": "desktop"},
    ]

    if info.os == "macOS":
        base.extend([
            {"path": str(home / "Pictures"), "category": "photos"},
            {"path": str(home / "Movies"), "category": "videos"},
            {"path": str(home / "Music"), "category": "music"},
        ])
    elif info.os == "Windows":
        base.extend([
            {"path": str(home / "Pictures"), "category": "photos"},
            {"path": str(home / "Videos"), "category": "videos"},
            {"path": str(home / "Music"), "category": "music"},
            {"path": str(home / "OneDrive"), "category": "onedrive"},
        ])
    else:
        base.extend([
            {"path": str(home / "Pictures"), "category": "photos"},
            {"path": str(home / "Videos"), "category": "videos"},
            {"path": str(home / "Music"), "category": "music"},
        ])

    return [f for f in base if Path(f["path"]).is_dir()]


def get_install_instructions() -> dict:
    """Return platform-specific installation instructions."""
    info = detect_platform()

    instructions = {
        "platform": info.os,
        "python_install": "",
        "package_install": "pip install doc-intelligence",
        "extras": "pip install 'doc-intelligence[all]'",
    }

    if info.os == "macOS":
        instructions["python_install"] = "brew install python3"
        instructions["notes"] = [
            "macOS Gatekeeper may prompt on first run — this is normal.",
            "For Spotlight integration, index files are stored in "
            f"{info.data_dir}.",
        ]
    elif info.os == "Windows":
        instructions["python_install"] = (
            "Download Python from https://python.org/downloads or "
            "winget install Python.Python.3.12"
        )
        instructions["notes"] = [
            "Run from PowerShell or Windows Terminal for best experience.",
            "Add to PATH during Python installation.",
        ]
    else:
        instructions["python_install"] = (
            "sudo apt install python3 python3-pip  # Debian/Ubuntu\n"
            "sudo dnf install python3 python3-pip  # Fedora"
        )
        instructions["notes"] = [
            "Works on all major distributions.",
            f"Config stored in {info.config_dir}.",
        ]

    return instructions


def ensure_dirs():
    """Create platform-specific directories if they don't exist."""
    info = detect_platform()
    info.config_dir.mkdir(parents=True, exist_ok=True)
    info.data_dir.mkdir(parents=True, exist_ok=True)
    info.cache_dir.mkdir(parents=True, exist_ok=True)
