"""Tests for PII detection module."""

import pytest
from src.ai.pii import scan_text, PIIMatch, PIIScanResult, _luhn_check


class TestLuhnCheck:
    def test_valid_visa(self):
        assert _luhn_check("4111111111111111") is True

    def test_valid_mastercard(self):
        assert _luhn_check("5500000000000004") is True

    def test_invalid_number(self):
        assert _luhn_check("1234567890123456") is False

    def test_too_short(self):
        assert _luhn_check("123456") is False

    def test_empty(self):
        assert _luhn_check("") is False


class TestScanTextSSN:
    def test_detects_ssn(self):
        result = scan_text("My SSN is 123-45-6789")
        assert result.has_pii
        assert "ssn" in result.pii_types_found

    def test_redacts_ssn(self):
        result = scan_text("SSN: 123-45-6789")
        ssn_match = [m for m in result.matches if m.pii_type == "ssn"][0]
        assert "6789" in ssn_match.value_redacted
        assert "123" not in ssn_match.value_redacted

    def test_ignores_invalid_ssn_area_000(self):
        result = scan_text("000-12-3456")
        ssn_matches = [m for m in result.matches if m.pii_type == "ssn"]
        assert len(ssn_matches) == 0

    def test_ignores_invalid_ssn_group_00(self):
        result = scan_text("123-00-6789")
        ssn_matches = [m for m in result.matches if m.pii_type == "ssn"]
        assert len(ssn_matches) == 0

    def test_ignores_invalid_ssn_serial_0000(self):
        result = scan_text("123-45-0000")
        ssn_matches = [m for m in result.matches if m.pii_type == "ssn"]
        assert len(ssn_matches) == 0

    def test_multiple_ssns(self):
        text = "SSN1: 123-45-6789\nSSN2: 987-65-4321"
        result = scan_text(text)
        ssn_matches = [m for m in result.matches if m.pii_type == "ssn"]
        assert len(ssn_matches) == 2


class TestScanTextCreditCard:
    def test_detects_valid_visa(self):
        result = scan_text("Card: 4111 1111 1111 1111")
        assert "credit_card" in result.pii_types_found

    def test_detects_dashed_format(self):
        result = scan_text("Card: 4111-1111-1111-1111")
        assert "credit_card" in result.pii_types_found

    def test_ignores_invalid_luhn(self):
        result = scan_text("Card: 1234 5678 9012 3456")
        cc_matches = [m for m in result.matches if m.pii_type == "credit_card"]
        assert len(cc_matches) == 0

    def test_redacts_card_number(self):
        result = scan_text("Card: 4111 1111 1111 1111")
        cc_match = [m for m in result.matches if m.pii_type == "credit_card"][0]
        assert "1111" in cc_match.value_redacted  # last 4
        assert "4111" not in cc_match.value_redacted  # first 4 hidden


class TestScanTextEmail:
    def test_detects_email(self):
        result = scan_text("Contact: user@example.com")
        assert "email" in result.pii_types_found

    def test_redacts_email(self):
        result = scan_text("Email: john.doe@company.org")
        email_match = [m for m in result.matches if m.pii_type == "email"][0]
        assert "company.org" in email_match.value_redacted
        assert "john.doe" not in email_match.value_redacted

    def test_detects_complex_email(self):
        result = scan_text("user.name+tag@sub.domain.co.uk")
        assert "email" in result.pii_types_found


class TestScanTextPhone:
    def test_detects_us_phone(self):
        result = scan_text("Call me at 555-123-4567")
        assert "phone" in result.pii_types_found

    def test_detects_phone_with_area_parens(self):
        result = scan_text("Phone: (555) 123-4567")
        assert "phone" in result.pii_types_found

    def test_redacts_phone(self):
        result = scan_text("Phone: 555-123-4567")
        phone_match = [m for m in result.matches if m.pii_type == "phone"][0]
        assert "4567" in phone_match.value_redacted


class TestScanTextIPAddress:
    def test_detects_ip(self):
        result = scan_text("Server at 192.168.1.100")
        assert "ip_address" in result.pii_types_found

    def test_redacts_ip(self):
        result = scan_text("IP: 10.0.0.1")
        ip_match = [m for m in result.matches if m.pii_type == "ip_address"][0]
        assert "10." in ip_match.value_redacted
        assert ".1" in ip_match.value_redacted


class TestScanTextDateOfBirth:
    def test_detects_dob(self):
        result = scan_text("Date of birth: 01/15/1990")
        assert "date_of_birth" in result.pii_types_found

    def test_detects_dob_abbrev(self):
        result = scan_text("DOB: 03-22-1985")
        assert "date_of_birth" in result.pii_types_found


class TestScanTextAddress:
    def test_detects_street_address(self):
        result = scan_text("Lives at 123 Main Street")
        assert "address" in result.pii_types_found

    def test_detects_various_suffixes(self):
        for suffix in ["Ave", "Blvd", "Dr", "Ln", "Rd", "Ct"]:
            result = scan_text(f"456 Oak {suffix}")
            assert "address" in result.pii_types_found, f"Failed for {suffix}"


class TestScanResultProperties:
    def test_no_pii_empty_text(self):
        result = scan_text("")
        assert not result.has_pii
        assert result.risk_level == "none"

    def test_no_pii_clean_text(self):
        result = scan_text("Hello world, this is a normal document.")
        assert not result.has_pii

    def test_high_risk_for_ssn(self):
        result = scan_text("SSN: 123-45-6789")
        assert result.risk_level == "high"

    def test_high_risk_for_credit_card(self):
        result = scan_text("Card: 4111 1111 1111 1111")
        assert result.risk_level == "high"

    def test_medium_risk_for_email(self):
        result = scan_text("Email: user@test.com")
        assert result.risk_level == "medium"

    def test_to_dict(self):
        result = scan_text("SSN: 123-45-6789", path="/test/file.txt")
        d = result.to_dict()
        assert d["path"] == "/test/file.txt"
        assert d["has_pii"] is True
        assert d["risk_level"] == "high"
        assert "ssn" in d["pii_types"]
        assert d["match_count"] >= 1

    def test_line_numbers(self):
        text = "Line 1\nLine 2\nSSN: 123-45-6789\nLine 4"
        result = scan_text(text)
        ssn_match = [m for m in result.matches if m.pii_type == "ssn"][0]
        assert ssn_match.line_number == 3

    def test_multiple_pii_types(self):
        text = "SSN: 123-45-6789\nEmail: test@example.com\nCard: 4111 1111 1111 1111"
        result = scan_text(text)
        assert len(result.pii_types_found) >= 3
        assert result.risk_level == "high"
