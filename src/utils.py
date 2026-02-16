"""
Shared utilities for doc-intelligence scripts.
"""

from pathlib import Path

import yaml


def load_config(config_path: str = None) -> dict:
    """Load configuration from YAML file.

    Args:
        config_path: Path to config file. Defaults to config/config.yaml
                     relative to the project root.
    """
    if config_path is None:
        # Walk up from this file (src/utils.py) to project root
        config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    else:
        config_path = Path(config_path)

    with open(config_path) as f:
        return yaml.safe_load(f)


def format_size(size_bytes: int) -> str:
    """Format bytes to human readable size."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"
