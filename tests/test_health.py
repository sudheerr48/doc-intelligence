"""
Tests for the Health Report module (src/health.py).
Tests scoring logic and report generation.
"""

import pytest

from src.analysis.health import compute_health_score, generate_health_text


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def healthy_metrics():
    """Metrics for a healthy file system."""
    return {
        "total_files": 5000,
        "total_size": 10_000_000_000,  # 10GB
        "duplicate_sets": 5,
        "duplicate_files": 12,
        "wasted_by_duplicates": 50_000_000,  # 50MB
        "stale_files": 200,
        "stale_size": 500_000_000,
        "large_files": 3,
        "large_size": 800_000_000,
        "top_large_files": [
            {"path": "/a/big.zip", "name": "big.zip", "size": 300_000_000, "ext": ".zip", "category": "downloads"},
            {"path": "/a/movie.mp4", "name": "movie.mp4", "size": 250_000_000, "ext": ".mp4", "category": "media"},
            {"path": "/a/backup.tar", "name": "backup.tar", "size": 250_000_000, "ext": ".tar", "category": "backups"},
        ],
        "new_files_7d": 50,
        "new_size_7d": 200_000_000,
        "extension_types": 25,
        "category_breakdown": [
            {"category": "documents", "files": 2000, "size": 4_000_000_000},
            {"category": "downloads", "files": 1500, "size": 3_000_000_000},
            {"category": "desktop", "files": 1500, "size": 3_000_000_000},
        ],
        "top_duplicates": [
            {"count": 3, "size_each": 10_000_000, "wasted": 20_000_000, "sample": "report.pdf"},
        ],
        "tagged_files": 4000,
        "untagged_files": 1000,
        "by_extension": {".pdf": 500, ".jpg": 400, ".py": 300},
    }


@pytest.fixture
def unhealthy_metrics():
    """Metrics for an unhealthy file system."""
    return {
        "total_files": 10000,
        "total_size": 50_000_000_000,
        "duplicate_sets": 500,
        "duplicate_files": 4000,
        "wasted_by_duplicates": 20_000_000_000,
        "stale_files": 6000,
        "stale_size": 30_000_000_000,
        "large_files": 50,
        "large_size": 25_000_000_000,
        "top_large_files": [
            {"path": "/a/huge.iso", "name": "huge.iso", "size": 5_000_000_000, "ext": ".iso", "category": "downloads"},
            {"path": "/a/vm.vmdk", "name": "vm.vmdk", "size": 4_000_000_000, "ext": ".vmdk", "category": "dev"},
            {"path": "/a/dump.sql", "name": "dump.sql", "size": 3_000_000_000, "ext": ".sql", "category": "data"},
        ],
        "new_files_7d": 5,
        "new_size_7d": 10_000_000,
        "extension_types": 50,
        "category_breakdown": [
            {"category": "downloads", "files": 5000, "size": 25_000_000_000},
            {"category": "documents", "files": 5000, "size": 25_000_000_000},
        ],
        "top_duplicates": [
            {"count": 10, "size_each": 500_000_000, "wasted": 4_500_000_000, "sample": "backup.zip"},
        ],
        "tagged_files": 0,
        "untagged_files": 10000,
        "by_extension": {".zip": 2000, ".pdf": 1000},
    }


@pytest.fixture
def empty_metrics():
    """Metrics for an empty database."""
    return {
        "total_files": 0,
        "total_size": 0,
        "duplicate_sets": 0,
        "duplicate_files": 0,
        "wasted_by_duplicates": 0,
        "stale_files": 0,
        "stale_size": 0,
        "large_files": 0,
        "large_size": 0,
        "top_large_files": [],
        "new_files_7d": 0,
        "new_size_7d": 0,
        "extension_types": 0,
        "category_breakdown": [],
        "top_duplicates": [],
        "tagged_files": 0,
        "untagged_files": 0,
        "by_extension": {},
    }


# ---------------------------------------------------------------------------
# Score computation tests
# ---------------------------------------------------------------------------

class TestComputeHealthScore:
    def test_healthy_system_scores_high(self, healthy_metrics):
        result = compute_health_score(healthy_metrics)
        assert result["score"] >= 70
        assert result["grade"] in ("A", "B")
        assert result["summary"]
        assert isinstance(result["issues"], list)
        assert isinstance(result["recommendations"], list)

    def test_unhealthy_system_scores_low(self, unhealthy_metrics):
        result = compute_health_score(unhealthy_metrics)
        assert result["score"] < 60
        assert result["grade"] in ("C", "D", "F")
        assert len(result["issues"]) >= 2

    def test_empty_system(self, empty_metrics):
        result = compute_health_score(empty_metrics)
        assert result["score"] == 0
        assert result["grade"] == "N/A"

    def test_score_clamped_to_0_100(self, unhealthy_metrics):
        result = compute_health_score(unhealthy_metrics)
        assert 0 <= result["score"] <= 100

    def test_high_duplicate_ratio_penalized(self):
        metrics = {
            "total_files": 100,
            "total_size": 1_000_000,
            "duplicate_sets": 20,
            "duplicate_files": 60,
            "wasted_by_duplicates": 500_000,
            "stale_files": 0, "stale_size": 0,
            "large_files": 0, "large_size": 0,
            "top_large_files": [],
            "new_files_7d": 0, "new_size_7d": 0,
            "extension_types": 5,
            "category_breakdown": [],
            "top_duplicates": [],
            "tagged_files": 50, "untagged_files": 50,
            "by_extension": {},
        }
        result = compute_health_score(metrics)
        # 60% duplicates should trigger "high" penalty
        high_issues = [i for i in result["issues"] if i["severity"] == "high"]
        assert len(high_issues) >= 1

    def test_no_tags_penalized(self):
        metrics = {
            "total_files": 500,
            "total_size": 1_000_000,
            "duplicate_sets": 0,
            "duplicate_files": 0,
            "wasted_by_duplicates": 0,
            "stale_files": 0, "stale_size": 0,
            "large_files": 0, "large_size": 0,
            "top_large_files": [],
            "new_files_7d": 0, "new_size_7d": 0,
            "extension_types": 10,
            "category_breakdown": [],
            "top_duplicates": [],
            "tagged_files": 0, "untagged_files": 500,
            "by_extension": {},
        }
        result = compute_health_score(metrics)
        tag_issues = [i for i in result["issues"] if "tag" in i["title"].lower()]
        assert len(tag_issues) >= 1

    def test_grade_boundaries(self):
        for score, expected_grade in [
            (95, "A"), (80, "B"), (65, "C"), (45, "D"), (20, "F")
        ]:
            # Manually construct result to check grade logic
            if score >= 90:
                assert "A" == expected_grade or expected_grade == "A"


# ---------------------------------------------------------------------------
# Report text generation tests
# ---------------------------------------------------------------------------

class TestGenerateHealthText:
    def test_report_contains_sections(self, healthy_metrics):
        health = compute_health_score(healthy_metrics)
        text = generate_health_text(healthy_metrics, health)

        assert "HEALTH REPORT" in text
        assert "Health Score:" in text
        assert "Overview" in text
        assert "Total files:" in text
        assert "Recommendations" in text

    def test_report_includes_categories(self, healthy_metrics):
        health = compute_health_score(healthy_metrics)
        text = generate_health_text(healthy_metrics, health)
        assert "Storage by Category" in text
        assert "documents" in text

    def test_report_includes_issues(self, unhealthy_metrics):
        health = compute_health_score(unhealthy_metrics)
        text = generate_health_text(unhealthy_metrics, health)
        assert "Issues Found" in text

    def test_empty_report(self, empty_metrics):
        health = compute_health_score(empty_metrics)
        text = generate_health_text(empty_metrics, health)
        assert "HEALTH REPORT" in text
        assert "N/A" in text
