"""
First-run onboarding experience.

Provides a guided setup wizard that:
  - Detects the user's OS and common folders
  - Lets the user pick which folders to scan
  - Auto-generates config.yaml
  - Runs the initial scan with progress display
  - Shows a "here's what I found" summary
"""

from .wizard import (
    is_first_run,
    run_onboarding,
    detect_default_folders,
    generate_config,
    first_run_summary,
)

__all__ = [
    "is_first_run",
    "run_onboarding",
    "detect_default_folders",
    "generate_config",
    "first_run_summary",
]
