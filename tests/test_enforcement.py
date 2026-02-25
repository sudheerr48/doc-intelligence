"""Tests for tier enforcement logic."""

import pytest
from src.licensing.tiers import (
    Tier, TIER_LIMITS, check_feature, check_file_limit,
    require_feature, require_file_limit,
    set_current_tier, get_current_tier, get_upgrade_message,
)


@pytest.fixture(autouse=True)
def reset_tier():
    """Reset tier to FREE before each test."""
    set_current_tier(Tier.FREE)
    yield
    set_current_tier(Tier.FREE)


class TestCheckFeature:
    def test_free_tier_allows_duplicates(self):
        set_current_tier(Tier.FREE)
        assert check_feature("duplicate_detection") is True

    def test_free_tier_allows_health(self):
        set_current_tier(Tier.FREE)
        assert check_feature("health_report") is True

    def test_free_tier_blocks_ai_tagging(self):
        set_current_tier(Tier.FREE)
        assert check_feature("ai_tagging") is False

    def test_free_tier_blocks_pii(self):
        set_current_tier(Tier.FREE)
        assert check_feature("pii_detection") is False

    def test_free_tier_blocks_semantic_search(self):
        set_current_tier(Tier.FREE)
        assert check_feature("semantic_search") is False

    def test_free_tier_blocks_image_classification(self):
        set_current_tier(Tier.FREE)
        assert check_feature("image_classification") is False

    def test_free_tier_blocks_mcp(self):
        set_current_tier(Tier.FREE)
        assert check_feature("mcp_server") is False

    def test_pro_tier_allows_ai_tagging(self):
        set_current_tier(Tier.PRO)
        assert check_feature("ai_tagging") is True

    def test_pro_tier_allows_pii(self):
        set_current_tier(Tier.PRO)
        assert check_feature("pii_detection") is True

    def test_pro_tier_allows_semantic_search(self):
        set_current_tier(Tier.PRO)
        assert check_feature("semantic_search") is True

    def test_pro_tier_allows_mcp(self):
        set_current_tier(Tier.PRO)
        assert check_feature("mcp_server") is True

    def test_team_tier_allows_everything(self):
        set_current_tier(Tier.TEAM)
        for feature in TIER_LIMITS[Tier.TEAM]:
            if feature != "max_files":
                assert check_feature(feature) is True

    def test_unknown_feature_returns_false(self):
        set_current_tier(Tier.FREE)
        assert check_feature("nonexistent_feature") is False


class TestCheckFileLimit:
    def test_free_tier_allows_under_limit(self):
        set_current_tier(Tier.FREE)
        allowed, max_files = check_file_limit(500)
        assert allowed is True
        assert max_files == 1000

    def test_free_tier_blocks_at_limit(self):
        set_current_tier(Tier.FREE)
        allowed, max_files = check_file_limit(1000)
        assert allowed is False
        assert max_files == 1000

    def test_free_tier_blocks_over_limit(self):
        set_current_tier(Tier.FREE)
        allowed, max_files = check_file_limit(1500)
        assert allowed is False

    def test_pro_tier_unlimited(self):
        set_current_tier(Tier.PRO)
        allowed, max_files = check_file_limit(999999)
        assert allowed is True
        assert max_files is None

    def test_team_tier_unlimited(self):
        set_current_tier(Tier.TEAM)
        allowed, max_files = check_file_limit(999999)
        assert allowed is True
        assert max_files is None


class TestRequireFeature:
    def test_allowed_returns_true_empty_msg(self):
        set_current_tier(Tier.PRO)
        allowed, msg = require_feature("ai_tagging")
        assert allowed is True
        assert msg == ""

    def test_blocked_returns_false_with_message(self):
        set_current_tier(Tier.FREE)
        allowed, msg = require_feature("ai_tagging")
        assert allowed is False
        assert "Pro license" in msg
        assert "activate" in msg

    def test_blocked_message_includes_feature_name(self):
        set_current_tier(Tier.FREE)
        allowed, msg = require_feature("pii_detection")
        assert "pii detection" in msg


class TestRequireFileLimit:
    def test_allowed_returns_true(self):
        set_current_tier(Tier.PRO)
        allowed, msg = require_file_limit(50000)
        assert allowed is True
        assert msg == ""

    def test_blocked_returns_count_info(self):
        set_current_tier(Tier.FREE)
        allowed, msg = require_file_limit(1000)
        assert allowed is False
        assert "1,000" in msg
        assert "Pro" in msg


class TestUpgradeMessage:
    def test_includes_feature(self):
        msg = get_upgrade_message("pii detection")
        assert "pii detection" in msg

    def test_includes_url(self):
        msg = get_upgrade_message("ai")
        assert "doc-intelligence.dev" in msg

    def test_includes_activate_command(self):
        msg = get_upgrade_message("ai")
        assert "activate" in msg
