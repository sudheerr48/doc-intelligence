"""
PII (Personally Identifiable Information) detection in file content.

Scans extracted text for sensitive data patterns:
  - Social Security Numbers (SSN)
  - Credit/debit card numbers (Luhn-validated)
  - Email addresses
  - Phone numbers (US formats)
  - IP addresses
  - Dates of birth patterns
  - Street addresses (US)

Works offline with regex — no API calls required.
Optional AI-enhanced detection available with an LLM provider.
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PIIMatch:
    """A single PII detection result."""
    pii_type: str
    value_redacted: str  # partially masked
    line_number: Optional[int] = None
    confidence: float = 1.0


@dataclass
class PIIScanResult:
    """Results of scanning a single file for PII."""
    path: str
    matches: list[PIIMatch] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def has_pii(self) -> bool:
        return len(self.matches) > 0

    @property
    def pii_types_found(self) -> set[str]:
        return {m.pii_type for m in self.matches}

    @property
    def risk_level(self) -> str:
        types = self.pii_types_found
        if types & {"ssn", "credit_card"}:
            return "high"
        if types & {"email", "phone", "date_of_birth"}:
            return "medium"
        if types:
            return "low"
        return "none"

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "has_pii": self.has_pii,
            "risk_level": self.risk_level,
            "pii_types": sorted(self.pii_types_found),
            "match_count": len(self.matches),
            "matches": [
                {
                    "type": m.pii_type,
                    "value": m.value_redacted,
                    "line": m.line_number,
                    "confidence": m.confidence,
                }
                for m in self.matches
            ],
        }


# ------------------------------------------------------------------
# Regex patterns
# ------------------------------------------------------------------

_SSN_RE = re.compile(
    r"\b(\d{3})-(\d{2})-(\d{4})\b"
)

_CC_RE = re.compile(
    r"\b(\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4})\b"
)

_EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
)

_PHONE_RE = re.compile(
    r"\b(?:\+?1[\s\-.]?)?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}\b"
)

_IP_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
)

_DOB_RE = re.compile(
    r"\b(?:date\s+of\s+birth|dob|born|birthday)"
    r"\s*[:=]?\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})\b",
    re.IGNORECASE,
)

_ADDRESS_RE = re.compile(
    r"\b\d{1,5}\s+[A-Za-z]+(?:\s+[A-Za-z]+){0,3}\s+"
    r"(?:St|Street|Ave|Avenue|Blvd|Boulevard|Dr|Drive|Ln|Lane|Rd|Road|Ct|Court"
    r"|Way|Pl|Place|Cir|Circle)\.?\b",
    re.IGNORECASE,
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _redact(value: str, keep_start: int = 0, keep_end: int = 4) -> str:
    """Mask middle of a value, keeping start/end chars visible."""
    clean = value.replace(" ", "").replace("-", "")
    if len(clean) <= keep_start + keep_end:
        return "*" * len(clean)
    return (
        clean[:keep_start]
        + "*" * (len(clean) - keep_start - keep_end)
        + clean[-keep_end:]
    )


def _luhn_check(number_str: str) -> bool:
    """Validate credit card number with Luhn algorithm."""
    digits = [int(d) for d in number_str if d.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


# ------------------------------------------------------------------
# Core scanner
# ------------------------------------------------------------------

def scan_text(text: str, path: str = "<unknown>") -> PIIScanResult:
    """Scan a text string for PII patterns.

    Args:
        text: The extracted text content to scan.
        path: File path (for labeling results).

    Returns:
        PIIScanResult with all matches found.
    """
    if not text:
        return PIIScanResult(path=path)

    matches: list[PIIMatch] = []
    lines = text.split("\n")

    for line_num, line in enumerate(lines, 1):
        # SSN
        for m in _SSN_RE.finditer(line):
            area, group, serial = m.group(1), m.group(2), m.group(3)
            # Filter out obviously invalid SSNs
            if area == "000" or group == "00" or serial == "0000":
                continue
            matches.append(PIIMatch(
                pii_type="ssn",
                value_redacted=f"***-**-{serial}",
                line_number=line_num,
                confidence=0.95,
            ))

        # Credit cards (Luhn validated)
        for m in _CC_RE.finditer(line):
            raw = m.group(1)
            digits_only = re.sub(r"[\s\-]", "", raw)
            if _luhn_check(digits_only):
                matches.append(PIIMatch(
                    pii_type="credit_card",
                    value_redacted=_redact(digits_only, keep_start=0, keep_end=4),
                    line_number=line_num,
                    confidence=0.9,
                ))

        # Email
        for m in _EMAIL_RE.finditer(line):
            email = m.group(0)
            local, domain = email.rsplit("@", 1)
            redacted = f"{local[0]}***@{domain}"
            matches.append(PIIMatch(
                pii_type="email",
                value_redacted=redacted,
                line_number=line_num,
                confidence=0.85,
            ))

        # Phone
        for m in _PHONE_RE.finditer(line):
            phone = m.group(0)
            digits = re.sub(r"\D", "", phone)
            if len(digits) >= 10:
                matches.append(PIIMatch(
                    pii_type="phone",
                    value_redacted=f"***-***-{digits[-4:]}",
                    line_number=line_num,
                    confidence=0.7,
                ))

        # IP addresses
        for m in _IP_RE.finditer(line):
            ip = m.group(0)
            parts = ip.split(".")
            matches.append(PIIMatch(
                pii_type="ip_address",
                value_redacted=f"{parts[0]}.***.***.{parts[3]}",
                line_number=line_num,
                confidence=0.6,
            ))

        # Date of birth
        for m in _DOB_RE.finditer(line):
            matches.append(PIIMatch(
                pii_type="date_of_birth",
                value_redacted="**/**/****",
                line_number=line_num,
                confidence=0.75,
            ))

        # Street addresses
        for m in _ADDRESS_RE.finditer(line):
            addr = m.group(0)
            matches.append(PIIMatch(
                pii_type="address",
                value_redacted=f"{addr[:3]}*** {addr.split()[-1]}",
                line_number=line_num,
                confidence=0.6,
            ))

    return PIIScanResult(path=path, matches=matches)


def scan_files(db, limit: int = 500) -> list[PIIScanResult]:
    """Scan indexed files with extracted text for PII.

    Args:
        db: FileDatabase instance.
        limit: Max files to scan.

    Returns:
        List of PIIScanResult for files that contain PII.
    """
    rows = db.conn.execute("""
        SELECT path, content_text FROM files
        WHERE content_text IS NOT NULL AND LENGTH(content_text) > 0
        ORDER BY size_bytes DESC
        LIMIT ?
    """, [limit]).fetchall()

    results = []
    for path, text in rows:
        result = scan_text(text, path=path)
        if result.has_pii:
            results.append(result)

    return results


def scan_files_summary(db, limit: int = 500) -> dict:
    """Return an aggregate PII summary across all indexed files."""
    results = scan_files(db, limit=limit)

    type_counts: dict[str, int] = {}
    risk_counts = {"high": 0, "medium": 0, "low": 0}
    total_matches = 0

    for r in results:
        risk_counts[r.risk_level] = risk_counts.get(r.risk_level, 0) + 1
        total_matches += len(r.matches)
        for t in r.pii_types_found:
            type_counts[t] = type_counts.get(t, 0) + 1

    return {
        "files_scanned": limit,
        "files_with_pii": len(results),
        "total_matches": total_matches,
        "risk_breakdown": risk_counts,
        "type_counts": type_counts,
        "high_risk_files": [
            r.to_dict() for r in results if r.risk_level == "high"
        ],
    }
