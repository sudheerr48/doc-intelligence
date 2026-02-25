"""
License key generation, validation, and storage.

Keys are HMAC-signed tokens containing tier + expiry information.
Validation is local-only — no network calls needed.

Key format: DI-<tier>-<expiry_hex>-<payload_hex>-<signature_hex>
Example:    DI-PRO-67A1B2C3-A1B2C3D4E5F6-1A2B3C4D5E6F7A8B
"""

import hashlib
import hmac
import json
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# Default signing secret (override via DOC_INTELLIGENCE_LICENSE_SECRET env var)
_DEFAULT_SECRET = b"doc-intelligence-v5-license-key-secret"


@dataclass
class LicenseInfo:
    """Parsed license key information."""
    tier: str
    expires_at: Optional[float]  # Unix timestamp, None = never
    valid: bool
    error: Optional[str] = None

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    @property
    def days_remaining(self) -> Optional[int]:
        if self.expires_at is None:
            return None
        remaining = self.expires_at - time.time()
        return max(0, int(remaining / 86400))


def _get_secret() -> bytes:
    """Get the signing secret from environment or default."""
    import os
    secret = os.environ.get("DOC_INTELLIGENCE_LICENSE_SECRET", "")
    if secret:
        return secret.encode()
    return _DEFAULT_SECRET


def generate_license_key(
    tier: str = "pro",
    days: Optional[int] = 365,
    secret: Optional[bytes] = None,
) -> str:
    """Generate a signed license key.

    Args:
        tier: License tier (pro, team).
        days: Days until expiry. None for perpetual.
        secret: Signing secret (defaults to env/built-in).

    Returns:
        License key string.
    """
    if secret is None:
        secret = _get_secret()

    tier_upper = tier.upper()
    if tier_upper not in ("PRO", "TEAM"):
        raise ValueError(f"Invalid tier: {tier}")

    if days is not None:
        expires_at = int(time.time()) + (days * 86400)
    else:
        expires_at = 0  # 0 = perpetual

    # Payload: tier + expiry packed
    payload = struct.pack(">I", expires_at) + tier_upper.encode()
    payload_hex = payload.hex().upper()

    # Expiry as hex
    expiry_hex = f"{expires_at:08X}"

    # HMAC signature
    sig = hmac.new(secret, payload, hashlib.sha256).digest()[:8]
    sig_hex = sig.hex().upper()

    return f"DI-{tier_upper}-{expiry_hex}-{payload_hex}-{sig_hex}"


def validate_license_key(
    key: str,
    secret: Optional[bytes] = None,
) -> LicenseInfo:
    """Validate a license key and return parsed info.

    Args:
        key: License key string.
        secret: Signing secret (defaults to env/built-in).

    Returns:
        LicenseInfo with validation result.
    """
    if secret is None:
        secret = _get_secret()

    try:
        parts = key.strip().split("-")
        if len(parts) != 5 or parts[0] != "DI":
            return LicenseInfo(
                tier="free", expires_at=None, valid=False,
                error="Invalid key format",
            )

        _, tier_str, expiry_hex, payload_hex, sig_hex = parts
        tier_str = tier_str.upper()

        if tier_str not in ("PRO", "TEAM"):
            return LicenseInfo(
                tier="free", expires_at=None, valid=False,
                error=f"Unknown tier: {tier_str}",
            )

        # Reconstruct payload
        payload = bytes.fromhex(payload_hex)
        expected_sig = hmac.new(secret, payload, hashlib.sha256).digest()[:8]

        # Verify signature
        actual_sig = bytes.fromhex(sig_hex)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return LicenseInfo(
                tier="free", expires_at=None, valid=False,
                error="Invalid signature",
            )

        # Parse expiry
        expires_at = int(expiry_hex, 16)
        if expires_at == 0:
            expires_at_val = None  # perpetual
        else:
            expires_at_val = float(expires_at)

        info = LicenseInfo(
            tier=tier_str.lower(),
            expires_at=expires_at_val,
            valid=True,
        )

        if info.is_expired:
            info.valid = False
            info.error = "License has expired"

        return info

    except Exception as e:
        return LicenseInfo(
            tier="free", expires_at=None, valid=False,
            error=f"Validation error: {e}",
        )


# ------------------------------------------------------------------
# Persistent license storage
# ------------------------------------------------------------------

def _license_file() -> Path:
    """Path to the stored license file."""
    return Path.home() / ".config" / "doc-intelligence" / "license.json"


def store_license(key: str) -> LicenseInfo:
    """Validate and store a license key to disk.

    Args:
        key: License key string.

    Returns:
        LicenseInfo with validation result.
    """
    info = validate_license_key(key)
    if info.valid:
        path = _license_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "key": key,
            "tier": info.tier,
            "expires_at": info.expires_at,
            "stored_at": time.time(),
        }
        path.write_text(json.dumps(data, indent=2))

        # Update the active tier
        from .tiers import set_current_tier, Tier
        set_current_tier(Tier(info.tier))

    return info


def load_stored_license() -> Optional[LicenseInfo]:
    """Load and validate the stored license from disk."""
    path = _license_file()
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text())
        key = data.get("key", "")
        return validate_license_key(key)
    except Exception:
        return None


def clear_license() -> bool:
    """Remove the stored license file."""
    path = _license_file()
    if path.exists():
        path.unlink()
        from .tiers import set_current_tier, Tier
        set_current_tier(Tier.FREE)
        return True
    return False
