"""
Smart folder / organization suggestions based on file metadata and tags.

Analyzes the file index to suggest:
  - Folder consolidation (scattered files that belong together)
  - Tag-based grouping ("47 files look like tax documents")
  - Large file cleanup candidates
  - Category-based organization recommendations
"""

from collections import defaultdict
from pathlib import Path
from typing import Optional


def suggest_organization(db, max_suggestions: int = 20) -> list[dict]:
    """Analyze file index and return actionable organization suggestions.

    Args:
        db: FileDatabase instance.
        max_suggestions: Maximum suggestions to return.

    Returns:
        List of suggestion dicts with type, description, files, and action.
    """
    suggestions: list[dict] = []

    suggestions.extend(_suggest_tag_groups(db))
    suggestions.extend(_suggest_scattered_files(db))
    suggestions.extend(_suggest_old_downloads(db))
    suggestions.extend(_suggest_large_file_cleanup(db))
    suggestions.extend(_suggest_empty_category_cleanup(db))

    # Sort by file count (most impactful first)
    suggestions.sort(key=lambda s: s.get("file_count", 0), reverse=True)
    return suggestions[:max_suggestions]


def _suggest_tag_groups(db) -> list[dict]:
    """Suggest grouping files that share the same tags."""
    all_tags = db.get_all_tags()
    suggestions = []

    # Focus on tags with significant file counts
    for tag, count in all_tags.items():
        if count < 5:
            continue

        files = db.get_files_by_tag(tag, limit=200)
        if len(files) < 5:
            continue

        # Check if files are spread across multiple directories
        dirs = set()
        for f in files:
            dirs.add(str(Path(f["path"]).parent))

        if len(dirs) >= 3:
            sample_files = [f["name"] for f in files[:5]]
            suggestions.append({
                "type": "tag_group",
                "priority": "medium",
                "title": f'Group "{tag}" files together',
                "description": (
                    f"{count} files tagged '{tag}' are spread across "
                    f"{len(dirs)} different folders."
                ),
                "suggestion": (
                    f"Consider creating a dedicated '{tag}' folder to "
                    f"consolidate these files."
                ),
                "file_count": count,
                "sample_files": sample_files,
                "tag": tag,
            })

    return suggestions


def _suggest_scattered_files(db) -> list[dict]:
    """Find files of the same type scattered across many directories."""
    rows = db.conn.execute("""
        SELECT extension, COUNT(*) as cnt,
               COUNT(DISTINCT substring(path, 1, length(path) - length(name))) as dir_count
        FROM files
        WHERE extension IS NOT NULL AND extension != ''
        GROUP BY extension
        HAVING cnt >= 10 AND dir_count >= 5
        ORDER BY cnt DESC
        LIMIT 10
    """).fetchall()

    suggestions = []
    for ext, count, dir_count in rows:
        if ext in (".py", ".js", ".ts", ".go", ".rs", ".c", ".h", ".java"):
            continue  # Skip source code — expected to be scattered

        suggestions.append({
            "type": "scattered_type",
            "priority": "low",
            "title": f"Consolidate {ext} files",
            "description": (
                f"{count} {ext} files are spread across {dir_count} folders."
            ),
            "suggestion": (
                f"Consider organizing {ext} files into a dedicated directory."
            ),
            "file_count": count,
            "extension": ext,
        })

    return suggestions


def _suggest_old_downloads(db) -> list[dict]:
    """Suggest cleaning up old files in Downloads-type categories."""
    rows = db.conn.execute("""
        SELECT path, name, size_bytes, modified_at
        FROM files
        WHERE category = 'downloads'
          AND modified_at < CURRENT_TIMESTAMP - INTERVAL '180 days'
        ORDER BY size_bytes DESC
        LIMIT 50
    """).fetchall()

    if len(rows) < 3:
        return []

    total_size = sum(r[2] for r in rows)
    sample_files = [r[1] for r in rows[:5]]

    return [{
        "type": "old_downloads",
        "priority": "high",
        "title": "Clean up old Downloads",
        "description": (
            f"{len(rows)} files in Downloads haven't been touched in 6+ months, "
            f"using {_fmt_size(total_size)}."
        ),
        "suggestion": "Review and archive or delete these unused downloads.",
        "file_count": len(rows),
        "total_size": total_size,
        "sample_files": sample_files,
    }]


def _suggest_large_file_cleanup(db) -> list[dict]:
    """Identify large files that may be cleanup candidates."""
    rows = db.conn.execute("""
        SELECT path, name, size_bytes, extension, category
        FROM files
        WHERE size_bytes > 104857600
        ORDER BY size_bytes DESC
        LIMIT 20
    """).fetchall()

    if not rows:
        return []

    total_size = sum(r[2] for r in rows)

    return [{
        "type": "large_files",
        "priority": "medium",
        "title": f"Review {len(rows)} large files (>100MB)",
        "description": (
            f"{len(rows)} files over 100MB are using {_fmt_size(total_size)}."
        ),
        "suggestion": (
            "Consider compressing, archiving, or moving large files "
            "to external storage."
        ),
        "file_count": len(rows),
        "total_size": total_size,
        "sample_files": [f"{r[1]} ({_fmt_size(r[2])})" for r in rows[:5]],
    }]


def _suggest_empty_category_cleanup(db) -> list[dict]:
    """Suggest merging categories with very few files."""
    rows = db.conn.execute("""
        SELECT category, COUNT(*) as cnt
        FROM files
        WHERE category IS NOT NULL
        GROUP BY category
        HAVING cnt <= 5
        ORDER BY cnt ASC
    """).fetchall()

    if len(rows) < 2:
        return []

    small_cats = [r[0] for r in rows]
    total = sum(r[1] for r in rows)

    return [{
        "type": "small_categories",
        "priority": "low",
        "title": "Consolidate small categories",
        "description": (
            f"{len(small_cats)} categories have 5 or fewer files "
            f"({total} files total)."
        ),
        "suggestion": (
            f"Consider merging these into larger categories: "
            f"{', '.join(small_cats[:5])}"
        ),
        "file_count": total,
        "categories": small_cats,
    }]


def _fmt_size(size_bytes: int) -> str:
    """Format bytes to human-readable size."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"
