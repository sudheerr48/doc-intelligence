"""
Tier definitions and feature gating.
"""

from enum import Enum
from typing import Optional


class Tier(str, Enum):
    FREE = "free"
    PRO = "pro"
    TEAM = "team"


TIER_LIMITS = {
    Tier.FREE: {
        "max_files": 1_000,
        "ai_tagging": False,
        "pii_detection": False,
        "semantic_search": False,
        "image_classification": False,
        "smart_suggestions": True,  # basic suggestions only
        "health_report": True,
        "duplicate_detection": True,
        "real_time_watch": True,
        "export_csv": True,
        "mcp_server": False,
        "priority_support": False,
    },
    Tier.PRO: {
        "max_files": None,  # unlimited
        "ai_tagging": True,
        "pii_detection": True,
        "semantic_search": True,
        "image_classification": True,
        "smart_suggestions": True,
        "health_report": True,
        "duplicate_detection": True,
        "real_time_watch": True,
        "export_csv": True,
        "mcp_server": True,
        "priority_support": False,
    },
    Tier.TEAM: {
        "max_files": None,
        "ai_tagging": True,
        "pii_detection": True,
        "semantic_search": True,
        "image_classification": True,
        "smart_suggestions": True,
        "health_report": True,
        "duplicate_detection": True,
        "real_time_watch": True,
        "export_csv": True,
        "mcp_server": True,
        "priority_support": True,
    },
}

# Module-level cached tier
_current_tier: Optional[Tier] = None


def set_current_tier(tier: Tier) -> None:
    """Set the active tier (called during license validation)."""
    global _current_tier
    _current_tier = tier


def get_current_tier() -> Tier:
    """Get the currently active tier. Defaults to FREE."""
    global _current_tier
    if _current_tier is None:
        # Try loading from stored license
        from .keys import load_stored_license
        info = load_stored_license()
        if info and info.tier:
            _current_tier = Tier(info.tier)
        else:
            _current_tier = Tier.FREE
    return _current_tier


def check_feature(feature: str) -> bool:
    """Check if a feature is available in the current tier."""
    tier = get_current_tier()
    limits = TIER_LIMITS.get(tier, TIER_LIMITS[Tier.FREE])
    return limits.get(feature, False)


def check_file_limit(current_count: int) -> tuple[bool, Optional[int]]:
    """Check if adding more files would exceed the tier's file limit.

    Returns:
        (allowed, max_files) — max_files is None for unlimited tiers.
    """
    tier = get_current_tier()
    max_files = TIER_LIMITS[tier]["max_files"]
    if max_files is None:
        return (True, None)
    return (current_count < max_files, max_files)


def get_tier_display_name(tier: Tier) -> str:
    """Human-readable tier name."""
    return {
        Tier.FREE: "Free",
        Tier.PRO: "Pro",
        Tier.TEAM: "Team",
    }.get(tier, "Free")


def get_upgrade_message(feature: str) -> str:
    """Return a message prompting the user to upgrade."""
    return (
        f"The '{feature}' feature requires a Pro license.\n"
        f"Upgrade at https://doc-intelligence.dev/pricing\n"
        f"Or enter your license key: doc-intelligence activate <KEY>"
    )


def require_feature(feature: str) -> tuple[bool, str]:
    """Check if a feature is available. Returns (allowed, message).

    Use this as the standard enforcement gate in CLI commands and dashboard.
    """
    if check_feature(feature):
        return (True, "")
    return (False, get_upgrade_message(feature.replace("_", " ")))


def require_file_limit(current_count: int) -> tuple[bool, str]:
    """Check file limit. Returns (allowed, message) with count info."""
    allowed, max_files = check_file_limit(current_count)
    if allowed:
        return (True, "")
    return (
        False,
        f"Free tier limit reached: {current_count:,} / {max_files:,} files.\n"
        f"Upgrade to Pro for unlimited files.\n"
        f"  https://doc-intelligence.dev/pricing\n"
        f"  Or: doc-intelligence activate <KEY>"
    )
