"""Tests for telemetry module."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from src.telemetry.tracker import (
    is_telemetry_enabled,
    enable_telemetry,
    disable_telemetry,
    track_event,
    track_error,
    get_local_stats,
    _sanitize,
    _EVENTS_FILE,
    _PREFS_FILE,
)


@pytest.fixture(autouse=True)
def clean_telemetry(tmp_path, monkeypatch):
    """Use temp dir for telemetry files to avoid polluting real config."""
    monkeypatch.setattr(
        "src.telemetry.tracker._TELEMETRY_DIR", tmp_path,
    )
    monkeypatch.setattr(
        "src.telemetry.tracker._EVENTS_FILE", tmp_path / "telemetry.jsonl",
    )
    monkeypatch.setattr(
        "src.telemetry.tracker._PREFS_FILE", tmp_path / "telemetry_prefs.json",
    )
    yield


class TestOptInOut:
    def test_disabled_by_default(self):
        assert is_telemetry_enabled() is False

    def test_enable(self):
        enable_telemetry()
        assert is_telemetry_enabled() is True

    def test_disable_after_enable(self):
        enable_telemetry()
        disable_telemetry()
        assert is_telemetry_enabled() is False

    def test_disable_removes_events(self, tmp_path):
        enable_telemetry()
        track_event("test_event")
        events_file = tmp_path / "telemetry.jsonl"
        assert events_file.exists()
        disable_telemetry()
        assert not events_file.exists()


class TestTrackEvent:
    def test_no_tracking_when_disabled(self, tmp_path):
        track_event("test_event")
        events_file = tmp_path / "telemetry.jsonl"
        assert not events_file.exists()

    def test_tracks_when_enabled(self, tmp_path):
        enable_telemetry()
        track_event("scan_completed", {"file_count": 100})
        events_file = tmp_path / "telemetry.jsonl"
        assert events_file.exists()
        records = [json.loads(l) for l in events_file.read_text().strip().split("\n")]
        assert len(records) == 1
        assert records[0]["event"] == "scan_completed"
        assert records[0]["properties"]["file_count"] == 100

    def test_strips_paths_from_properties(self, tmp_path):
        enable_telemetry()
        track_event("test", {"safe": "hello", "unsafe": "/home/user/secret.txt"})
        events_file = tmp_path / "telemetry.jsonl"
        record = json.loads(events_file.read_text().strip())
        assert "safe" in record["properties"]
        assert "unsafe" not in record["properties"]

    def test_includes_platform_and_version(self, tmp_path):
        enable_telemetry()
        track_event("test")
        events_file = tmp_path / "telemetry.jsonl"
        record = json.loads(events_file.read_text().strip())
        assert "platform" in record
        assert "version" in record
        assert "timestamp" in record


class TestTrackError:
    def test_tracks_error_when_enabled(self, tmp_path):
        enable_telemetry()
        track_error("ValueError", "Something went wrong", "scan")
        events_file = tmp_path / "telemetry.jsonl"
        record = json.loads(events_file.read_text().strip())
        assert record["event"] == "error"
        assert record["error_type"] == "ValueError"
        assert record["context"] == "scan"


class TestLocalStats:
    def test_empty_stats(self):
        stats = get_local_stats()
        assert stats["total_events"] == 0
        assert stats["errors"] == 0

    def test_stats_after_events(self, tmp_path):
        enable_telemetry()
        track_event("scan")
        track_event("scan")
        track_event("search")
        track_error("Error", "msg")
        stats = get_local_stats()
        assert stats["total_events"] == 4
        assert stats["event_counts"]["scan"] == 2
        assert stats["event_counts"]["search"] == 1
        assert stats["errors"] == 1


class TestSanitize:
    def test_removes_paths(self):
        assert "<path>" in _sanitize("Error in /home/user/file.txt")

    def test_removes_emails(self):
        assert "<email>" in _sanitize("Contact user@example.com")

    def test_truncates_long_messages(self):
        long_msg = "x" * 1000
        assert len(_sanitize(long_msg)) <= 500
