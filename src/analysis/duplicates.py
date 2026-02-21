"""
Duplicate file staging and management.
"""

import os
import shutil
from pathlib import Path

STAGING_FOLDER = "_TO_DELETE"


def pick_keeper(paths: list[str], strategy: str = "newest") -> str:
    """Choose which file to keep from a set of duplicates."""
    if strategy == "shortest":
        return min(paths, key=len)
    best = paths[0]
    best_mtime = 0.0
    for p in paths:
        try:
            mtime = os.path.getmtime(p)
            if mtime > best_mtime:
                best_mtime = mtime
                best = p
        except OSError:
            continue
    return best


def stage_files(paths_to_stage: list[str], staging_root: str) -> list[dict]:
    """Move files to the staging folder, preserving directory structure."""
    staging = Path(staging_root)
    staging.mkdir(parents=True, exist_ok=True)
    results = []

    for original_path in paths_to_stage:
        original = Path(original_path)
        if not original.exists():
            results.append({
                "original": original_path, "staged": None,
                "success": False, "reason": "file not found",
            })
            continue

        relative = str(original).lstrip("/")
        dest = staging / relative
        dest.parent.mkdir(parents=True, exist_ok=True)

        try:
            shutil.move(str(original), str(dest))
            results.append({
                "original": original_path, "staged": str(dest),
                "success": True,
            })
        except (OSError, shutil.Error) as e:
            results.append({
                "original": original_path, "staged": None,
                "success": False, "reason": str(e),
            })

    return results


def auto_stage_duplicates(
    duplicates: list[dict],
    staging_root: str,
    strategy: str = "newest",
    dry_run: bool = False,
) -> dict:
    """Automatically stage duplicate files, keeping one copy per set."""
    kept = []
    to_stage = []
    total_bytes = 0

    for dup_group in duplicates:
        paths = dup_group["paths"]
        if len(paths) < 2:
            continue
        keeper = pick_keeper(paths, strategy)
        kept.append(keeper)

        size_each = dup_group["total_size"] // dup_group["count"]
        for p in paths:
            if p != keeper:
                to_stage.append(p)
                total_bytes += size_each

    if dry_run:
        return {
            "kept": kept,
            "staged": [
                {"original": p, "staged": None, "success": True}
                for p in to_stage
            ],
            "errors": [],
            "total_bytes_freed": total_bytes,
            "dry_run": True,
        }

    results = stage_files(to_stage, staging_root)
    errors = [r for r in results if not r["success"]]
    staged = [r for r in results if r["success"]]

    return {
        "kept": kept,
        "staged": staged,
        "errors": errors,
        "total_bytes_freed": total_bytes,
        "dry_run": False,
    }


def list_staged_files(staging_root: str) -> list[dict]:
    """List all files currently in the staging folder."""
    staging = Path(staging_root)
    if not staging.exists():
        return []
    files = []
    for f in staging.rglob("*"):
        if f.is_file():
            relative = f.relative_to(staging)
            original = "/" + str(relative)
            try:
                size = f.stat().st_size
            except OSError:
                size = 0
            files.append({
                "staged_path": str(f),
                "original_path": original,
                "size_bytes": size,
            })
    return files


def confirm_delete_staged(staging_root: str) -> dict:
    """Permanently delete all files in the staging folder."""
    staging = Path(staging_root)
    if not staging.exists():
        return {"deleted_count": 0, "deleted_bytes": 0, "errors": []}

    deleted_count = 0
    deleted_bytes = 0
    errors = []

    for f in staging.rglob("*"):
        if f.is_file():
            try:
                deleted_bytes += f.stat().st_size
                f.unlink()
                deleted_count += 1
            except OSError as e:
                errors.append({"path": str(f), "error": str(e)})

    if staging.exists():
        shutil.rmtree(str(staging), ignore_errors=True)

    return {
        "deleted_count": deleted_count,
        "deleted_bytes": deleted_bytes,
        "errors": errors,
    }


def restore_staged_files(staging_root: str) -> dict:
    """Restore all staged files back to their original locations."""
    staging = Path(staging_root)
    if not staging.exists():
        return {"restored_count": 0, "errors": []}

    restored = 0
    errors = []

    for f in staging.rglob("*"):
        if not f.is_file():
            continue
        relative = f.relative_to(staging)
        original = Path("/") / relative
        try:
            original.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), str(original))
            restored += 1
        except (OSError, shutil.Error) as e:
            errors.append({"path": str(f), "error": str(e)})

    if staging.exists():
        shutil.rmtree(str(staging), ignore_errors=True)

    return {"restored_count": restored, "errors": errors}
