"""
Health Report Module
Generates file system health reports with scoring, issue detection,
and actionable recommendations. Works standalone (no AI required),
with optional AI-enhanced insights when available.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from .utils import format_size


def compute_health_score(metrics: dict) -> dict:
    """
    Compute a health score (0-100) from file system metrics.
    Pure computation — no AI required.

    Args:
        metrics: Dict from FileDatabase.get_health_metrics()

    Returns:
        Dict with score, grade, summary, issues, recommendations
    """
    score = 100
    issues = []
    recommendations = []
    total = metrics["total_files"]

    if total == 0:
        return {
            "score": 0,
            "grade": "N/A",
            "summary": "No files indexed. Run a scan first.",
            "issues": [],
            "recommendations": ["Run 'doc-intelligence scan' to index your files."],
        }

    total_size = metrics["total_size"]

    # --- Duplicate penalty ---
    dup_ratio = metrics["duplicate_files"] / total if total > 0 else 0
    wasted = metrics["wasted_by_duplicates"]

    if dup_ratio > 0.3:
        score -= 25
        issues.append({
            "severity": "high",
            "title": "Excessive duplicates",
            "detail": (
                f"{metrics['duplicate_files']:,} duplicate files in "
                f"{metrics['duplicate_sets']:,} sets, wasting "
                f"{format_size(wasted)}."
            ),
        })
        recommendations.append(
            f"Run 'doc-intelligence duplicates --auto-stage' to stage "
            f"{metrics['duplicate_files']:,} duplicates for cleanup."
        )
    elif dup_ratio > 0.1:
        score -= 12
        issues.append({
            "severity": "medium",
            "title": "Moderate duplicates",
            "detail": (
                f"{metrics['duplicate_files']:,} duplicates wasting "
                f"{format_size(wasted)}."
            ),
        })
        recommendations.append(
            "Review duplicates with 'doc-intelligence duplicates' to reclaim space."
        )
    elif metrics["duplicate_sets"] > 0:
        score -= 3

    # --- Stale files penalty ---
    stale_ratio = metrics["stale_files"] / total if total > 0 else 0

    if stale_ratio > 0.5:
        score -= 15
        issues.append({
            "severity": "medium",
            "title": "Many stale files",
            "detail": (
                f"{metrics['stale_files']:,} files ({format_size(metrics['stale_size'])}) "
                f"haven't been modified in over a year."
            ),
        })
        recommendations.append(
            "Archive or remove stale files to keep your file system lean."
        )
    elif stale_ratio > 0.2:
        score -= 7
        issues.append({
            "severity": "low",
            "title": "Some stale files",
            "detail": (
                f"{metrics['stale_files']:,} files untouched for 365+ days."
            ),
        })

    # --- Large files penalty ---
    if metrics["large_files"] > 20:
        score -= 10
        issues.append({
            "severity": "medium",
            "title": "Many large files",
            "detail": (
                f"{metrics['large_files']:,} files over 100 MB, "
                f"totaling {format_size(metrics['large_size'])}."
            ),
        })
        top_names = [f["name"] for f in metrics["top_large_files"][:3]]
        recommendations.append(
            f"Review large files: {', '.join(top_names)}. "
            f"Consider compressing or moving to external storage."
        )
    elif metrics["large_files"] > 5:
        score -= 5

    # --- Untagged files penalty ---
    if metrics["total_files"] > 100 and metrics["tagged_files"] == 0:
        score -= 10
        issues.append({
            "severity": "low",
            "title": "No files tagged",
            "detail": "AI tagging not used yet. Tags help with organization and search.",
        })
        recommendations.append(
            "Run 'doc-intelligence tag' to auto-classify files with AI."
        )
    elif metrics["untagged_files"] > metrics["total_files"] * 0.5:
        score -= 5
        issues.append({
            "severity": "low",
            "title": "Many untagged files",
            "detail": f"{metrics['untagged_files']:,} files without AI tags.",
        })

    # --- Low diversity bonus (very focused system) ---
    if metrics["extension_types"] < 5 and total > 100:
        score = min(100, score + 3)

    # Clamp
    score = max(0, min(100, score))

    # Grade
    if score >= 90:
        grade = "A"
    elif score >= 75:
        grade = "B"
    elif score >= 60:
        grade = "C"
    elif score >= 40:
        grade = "D"
    else:
        grade = "F"

    # Summary
    summary_parts = [f"{total:,} files indexed ({format_size(total_size)})."]
    if metrics["duplicate_sets"] > 0:
        summary_parts.append(
            f"{metrics['duplicate_sets']:,} duplicate sets wasting {format_size(wasted)}."
        )
    if metrics["new_files_7d"] > 0:
        summary_parts.append(
            f"{metrics['new_files_7d']:,} new files added in the last 7 days."
        )

    if not recommendations:
        recommendations.append("Your file system looks healthy! Keep it up.")

    return {
        "score": score,
        "grade": grade,
        "summary": " ".join(summary_parts),
        "issues": issues,
        "recommendations": recommendations,
    }


def generate_health_text(metrics: dict, health: dict) -> str:
    """
    Generate a human-readable health report string.

    Args:
        metrics: Raw metrics from get_health_metrics()
        health: Health assessment from compute_health_score()

    Returns:
        Formatted text report
    """
    lines = []
    lines.append("=" * 60)
    lines.append("  DOC INTELLIGENCE — FILE SYSTEM HEALTH REPORT")
    lines.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 60)
    lines.append("")

    # Score
    lines.append(f"  Health Score:  {health['score']}/100  (Grade: {health['grade']})")
    lines.append(f"  {health['summary']}")
    lines.append("")

    # Quick stats
    lines.append("— Overview —")
    lines.append(f"  Total files:       {metrics['total_files']:>10,}")
    lines.append(f"  Total size:        {format_size(metrics['total_size']):>10}")
    lines.append(f"  File types:        {metrics['extension_types']:>10,}")
    lines.append(f"  Duplicate sets:    {metrics['duplicate_sets']:>10,}")
    lines.append(f"  Wasted space:      {format_size(metrics['wasted_by_duplicates']):>10}")
    lines.append(f"  Stale files (1y+): {metrics['stale_files']:>10,}")
    lines.append(f"  Large (>100MB):    {metrics['large_files']:>10,}")
    lines.append(f"  Tagged files:      {metrics['tagged_files']:>10,}")
    lines.append(f"  New (7 days):      {metrics['new_files_7d']:>10,}")
    lines.append("")

    # Category breakdown
    if metrics["category_breakdown"]:
        lines.append("— Storage by Category —")
        for cat in metrics["category_breakdown"]:
            lines.append(
                f"  {cat['category']:<20} {cat['files']:>8,} files  "
                f"{format_size(cat['size']):>10}"
            )
        lines.append("")

    # Top extensions
    if metrics["by_extension"]:
        lines.append("— Top File Types —")
        for ext, count in list(metrics["by_extension"].items())[:10]:
            lines.append(f"  {ext or '(none)':<12} {count:>8,} files")
        lines.append("")

    # Issues
    if health["issues"]:
        lines.append("— Issues Found —")
        for issue in health["issues"]:
            severity = issue["severity"].upper()
            lines.append(f"  [{severity}] {issue['title']}")
            lines.append(f"         {issue['detail']}")
        lines.append("")

    # Top duplicates
    if metrics["top_duplicates"]:
        lines.append("— Top Duplicate Groups —")
        for i, d in enumerate(metrics["top_duplicates"][:5], 1):
            lines.append(
                f"  {i}. {d['sample']} — {d['count']} copies, "
                f"{format_size(d['size_each'])} each, "
                f"wasting {format_size(d['wasted'])}"
            )
        lines.append("")

    # Top large files
    if metrics["top_large_files"]:
        lines.append("— Largest Files —")
        for i, f in enumerate(metrics["top_large_files"][:5], 1):
            lines.append(f"  {i}. {f['name']} — {format_size(f['size'])}")
        lines.append("")

    # Recommendations
    lines.append("— Recommendations —")
    for i, rec in enumerate(health["recommendations"], 1):
        lines.append(f"  {i}. {rec}")
    lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)
