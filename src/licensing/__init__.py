"""
Licensing & tier system for Doc Intelligence.

Tiers:
  - free: 1000 files, basic search, duplicate detection (no AI)
  - pro: Unlimited files, AI tagging, PII detection, semantic search
  - team: Pro features + shared dashboards, priority support

License keys are validated locally using HMAC signatures.
No network calls required for validation.
"""

from .tiers import Tier, get_current_tier, check_feature, TIER_LIMITS
from .keys import validate_license_key, generate_license_key, LicenseInfo

__all__ = [
    "Tier",
    "get_current_tier",
    "check_feature",
    "TIER_LIMITS",
    "validate_license_key",
    "generate_license_key",
    "LicenseInfo",
]
