"""Tests for licensing and tier system."""

import time
import pytest
from src.licensing.keys import generate_license_key, validate_license_key, LicenseInfo
from src.licensing.tiers import Tier, TIER_LIMITS, check_feature, get_tier_display_name


class TestLicenseKeyGeneration:
    def test_generates_key(self):
        key = generate_license_key(tier="pro", days=365)
        assert key.startswith("DI-PRO-")
        assert len(key.split("-")) == 5

    def test_generates_team_key(self):
        key = generate_license_key(tier="team", days=30)
        assert key.startswith("DI-TEAM-")

    def test_perpetual_key(self):
        key = generate_license_key(tier="pro", days=None)
        assert "DI-PRO-00000000" in key

    def test_invalid_tier_raises(self):
        with pytest.raises(ValueError):
            generate_license_key(tier="invalid")

    def test_custom_secret(self):
        key = generate_license_key(tier="pro", secret=b"custom-secret")
        assert key.startswith("DI-PRO-")


class TestLicenseKeyValidation:
    def test_valid_key(self):
        key = generate_license_key(tier="pro", days=365)
        info = validate_license_key(key)
        assert info.valid is True
        assert info.tier == "pro"
        assert info.error is None

    def test_valid_team_key(self):
        key = generate_license_key(tier="team", days=365)
        info = validate_license_key(key)
        assert info.valid is True
        assert info.tier == "team"

    def test_perpetual_key_no_expiry(self):
        key = generate_license_key(tier="pro", days=None)
        info = validate_license_key(key)
        assert info.valid is True
        assert info.expires_at is None
        assert info.is_expired is False
        assert info.days_remaining is None

    def test_days_remaining(self):
        key = generate_license_key(tier="pro", days=30)
        info = validate_license_key(key)
        assert info.days_remaining is not None
        assert 29 <= info.days_remaining <= 30

    def test_invalid_format(self):
        info = validate_license_key("not-a-valid-key")
        assert info.valid is False
        assert info.error is not None

    def test_wrong_prefix(self):
        info = validate_license_key("XX-PRO-00000000-AABBCCDD-11223344")
        assert info.valid is False

    def test_tampered_signature(self):
        key = generate_license_key(tier="pro", days=365)
        parts = key.split("-")
        parts[4] = "0000000000000000"  # tamper with signature
        tampered = "-".join(parts)
        info = validate_license_key(tampered)
        assert info.valid is False

    def test_wrong_secret(self):
        key = generate_license_key(tier="pro", days=365, secret=b"secret-a")
        info = validate_license_key(key, secret=b"secret-b")
        assert info.valid is False

    def test_matching_custom_secret(self):
        secret = b"my-custom-secret"
        key = generate_license_key(tier="pro", days=365, secret=secret)
        info = validate_license_key(key, secret=secret)
        assert info.valid is True


class TestTiers:
    def test_free_tier_limits(self):
        limits = TIER_LIMITS[Tier.FREE]
        assert limits["max_files"] == 1000
        assert limits["ai_tagging"] is False
        assert limits["pii_detection"] is False
        assert limits["duplicate_detection"] is True

    def test_pro_tier_limits(self):
        limits = TIER_LIMITS[Tier.PRO]
        assert limits["max_files"] is None  # unlimited
        assert limits["ai_tagging"] is True
        assert limits["pii_detection"] is True
        assert limits["semantic_search"] is True

    def test_team_tier_has_priority_support(self):
        limits = TIER_LIMITS[Tier.TEAM]
        assert limits["priority_support"] is True

    def test_free_tier_no_priority_support(self):
        limits = TIER_LIMITS[Tier.FREE]
        assert limits["priority_support"] is False

    def test_display_names(self):
        assert get_tier_display_name(Tier.FREE) == "Free"
        assert get_tier_display_name(Tier.PRO) == "Pro"
        assert get_tier_display_name(Tier.TEAM) == "Team"

    def test_tier_enum_values(self):
        assert Tier.FREE.value == "free"
        assert Tier.PRO.value == "pro"
        assert Tier.TEAM.value == "team"
