"""
Tests for src/staging.py - duplicate staging and cleanup logic.
"""

import os
import time
from pathlib import Path

import pytest

from src.staging import (
    pick_keeper,
    stage_files,
    auto_stage_duplicates,
    list_staged_files,
    confirm_delete_staged,
    restore_staged_files,
    STAGING_FOLDER,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_dup_group(paths, size_each=100):
    """Create a duplicate group dict matching FileDatabase.get_duplicates() format."""
    return {
        "hash": "fakehash",
        "count": len(paths),
        "total_size": size_each * len(paths),
        "wasted_size": size_each * (len(paths) - 1),
        "paths": paths,
    }


# ---------------------------------------------------------------------------
# pick_keeper
# ---------------------------------------------------------------------------

class TestPickKeeper:
    """Tests for the keeper-selection strategy."""

    def test_newest_strategy(self, tmp_path):
        old = tmp_path / "old.txt"
        old.write_text("old")
        # Ensure different mtime
        time.sleep(0.05)
        new = tmp_path / "new.txt"
        new.write_text("new")

        keeper = pick_keeper([str(old), str(new)], strategy="newest")
        assert keeper == str(new)

    def test_shortest_strategy(self):
        paths = ["/a/very/long/path/file.txt", "/short/f.txt"]
        keeper = pick_keeper(paths, strategy="shortest")
        assert keeper == "/short/f.txt"

    def test_single_file(self, tmp_path):
        f = tmp_path / "only.txt"
        f.write_text("only")
        assert pick_keeper([str(f)]) == str(f)

    def test_nonexistent_files_fallback(self):
        """When files don't exist, should still return something."""
        paths = ["/no/such/a.txt", "/no/such/b.txt"]
        result = pick_keeper(paths, strategy="newest")
        assert result in paths


# ---------------------------------------------------------------------------
# stage_files
# ---------------------------------------------------------------------------

class TestStageFiles:
    """Tests for moving files to staging folder."""

    def test_stages_files_successfully(self, tmp_path):
        staging = tmp_path / STAGING_FOLDER
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("alpha")
        f2.write_text("beta")

        results = stage_files([str(f1), str(f2)], str(staging))

        assert len(results) == 2
        assert all(r["success"] for r in results)
        # Original files should no longer exist
        assert not f1.exists()
        assert not f2.exists()
        # Files should be in staging
        assert staging.exists()

    def test_preserves_directory_structure(self, tmp_path):
        staging = tmp_path / STAGING_FOLDER
        subdir = tmp_path / "sub" / "dir"
        subdir.mkdir(parents=True)
        f = subdir / "file.txt"
        f.write_text("hello")

        results = stage_files([str(f)], str(staging))
        assert results[0]["success"]

        # The staged file should preserve the path structure
        staged_path = Path(results[0]["staged"])
        assert staged_path.exists()
        assert staged_path.read_text() == "hello"

    def test_nonexistent_file_fails(self, tmp_path):
        staging = tmp_path / STAGING_FOLDER
        results = stage_files(["/nonexistent/file.txt"], str(staging))
        assert len(results) == 1
        assert not results[0]["success"]
        assert results[0]["reason"] == "file not found"

    def test_empty_list(self, tmp_path):
        staging = tmp_path / STAGING_FOLDER
        results = stage_files([], str(staging))
        assert results == []


# ---------------------------------------------------------------------------
# auto_stage_duplicates
# ---------------------------------------------------------------------------

class TestAutoStageDuplicates:
    """Tests for automatic duplicate staging."""

    def test_auto_stage_keeps_one(self, tmp_path):
        staging = tmp_path / STAGING_FOLDER

        # Create 3 duplicate files
        files = []
        for name in ["orig.txt", "copy1.txt", "copy2.txt"]:
            f = tmp_path / name
            f.write_text("duplicate content")
            files.append(str(f))

        duplicates = [make_dup_group(files)]
        result = auto_stage_duplicates(duplicates, str(staging))

        assert len(result["kept"]) == 1
        assert len(result["staged"]) == 2
        assert not result["dry_run"]

        # Keeper should still exist
        assert Path(result["kept"][0]).exists()
        # Other files should be gone from original location
        staged_originals = {s["original"] for s in result["staged"]}
        for orig in staged_originals:
            assert not Path(orig).exists()

    def test_dry_run_no_files_moved(self, tmp_path):
        staging = tmp_path / STAGING_FOLDER

        files = []
        for name in ["a.txt", "b.txt"]:
            f = tmp_path / name
            f.write_text("dup")
            files.append(str(f))

        duplicates = [make_dup_group(files)]
        result = auto_stage_duplicates(duplicates, str(staging), dry_run=True)

        assert result["dry_run"] is True
        assert len(result["kept"]) == 1
        assert len(result["staged"]) == 1
        # Files should still exist in original location
        for path in files:
            assert Path(path).exists()

    def test_multiple_duplicate_groups(self, tmp_path):
        staging = tmp_path / STAGING_FOLDER

        group1 = []
        for name in ["g1a.txt", "g1b.txt"]:
            f = tmp_path / name
            f.write_text("group1")
            group1.append(str(f))

        group2 = []
        for name in ["g2a.txt", "g2b.txt", "g2c.txt"]:
            f = tmp_path / name
            f.write_text("group2")
            group2.append(str(f))

        duplicates = [make_dup_group(group1), make_dup_group(group2)]
        result = auto_stage_duplicates(duplicates, str(staging))

        assert len(result["kept"]) == 2
        assert len(result["staged"]) == 3  # 1 from group1 + 2 from group2

    def test_empty_duplicates(self, tmp_path):
        staging = tmp_path / STAGING_FOLDER
        result = auto_stage_duplicates([], str(staging))
        assert len(result["kept"]) == 0
        assert len(result["staged"]) == 0

    def test_bytes_freed_calculated(self, tmp_path):
        staging = tmp_path / STAGING_FOLDER

        files = []
        for name in ["a.txt", "b.txt", "c.txt"]:
            f = tmp_path / name
            f.write_text("x" * 500)
            files.append(str(f))

        duplicates = [make_dup_group(files, size_each=500)]
        result = auto_stage_duplicates(duplicates, str(staging), dry_run=True)

        # 2 copies staged, 500 bytes each
        assert result["total_bytes_freed"] == 1000


# ---------------------------------------------------------------------------
# list_staged_files
# ---------------------------------------------------------------------------

class TestListStagedFiles:
    """Tests for listing staged files."""

    def test_lists_staged_files(self, tmp_path):
        staging = tmp_path / STAGING_FOLDER
        sub = staging / "home" / "user"
        sub.mkdir(parents=True)
        (sub / "file.txt").write_text("hello")
        (sub / "other.txt").write_text("world")

        files = list_staged_files(str(staging))
        assert len(files) == 2

        names = {Path(f["staged_path"]).name for f in files}
        assert names == {"file.txt", "other.txt"}

    def test_empty_staging(self, tmp_path):
        staging = tmp_path / STAGING_FOLDER
        files = list_staged_files(str(staging))
        assert files == []

    def test_reconstructs_original_path(self, tmp_path):
        staging = tmp_path / STAGING_FOLDER
        sub = staging / "home" / "user" / "docs"
        sub.mkdir(parents=True)
        (sub / "report.pdf").write_text("content")

        files = list_staged_files(str(staging))
        assert len(files) == 1
        assert files[0]["original_path"] == "/home/user/docs/report.pdf"


# ---------------------------------------------------------------------------
# confirm_delete_staged
# ---------------------------------------------------------------------------

class TestConfirmDeleteStaged:
    """Tests for permanent deletion of staged files."""

    def test_deletes_all_staged(self, tmp_path):
        staging = tmp_path / STAGING_FOLDER
        sub = staging / "data"
        sub.mkdir(parents=True)
        (sub / "a.txt").write_text("aaa")
        (sub / "b.txt").write_text("bbb")

        result = confirm_delete_staged(str(staging))
        assert result["deleted_count"] == 2
        assert result["deleted_bytes"] > 0
        assert not staging.exists()

    def test_empty_staging_no_error(self, tmp_path):
        staging = tmp_path / STAGING_FOLDER
        result = confirm_delete_staged(str(staging))
        assert result["deleted_count"] == 0
        assert result["deleted_bytes"] == 0

    def test_removes_staging_directory(self, tmp_path):
        staging = tmp_path / STAGING_FOLDER
        staging.mkdir()
        (staging / "file.txt").write_text("x")

        confirm_delete_staged(str(staging))
        assert not staging.exists()


# ---------------------------------------------------------------------------
# restore_staged_files
# ---------------------------------------------------------------------------

class TestRestoreStagedFiles:
    """Tests for restoring staged files."""

    def test_restores_to_original(self, tmp_path):
        staging = tmp_path / STAGING_FOLDER

        # Create a file and stage it
        original = tmp_path / "docs" / "file.txt"
        original.parent.mkdir(parents=True)
        original.write_text("important data")

        stage_files([str(original)], str(staging))
        assert not original.exists()

        # Restore
        result = restore_staged_files(str(staging))
        assert result["restored_count"] == 1
        assert original.exists()
        assert original.read_text() == "important data"

    def test_restore_empty_staging(self, tmp_path):
        staging = tmp_path / STAGING_FOLDER
        result = restore_staged_files(str(staging))
        assert result["restored_count"] == 0

    def test_cleans_up_staging_dir(self, tmp_path):
        staging = tmp_path / STAGING_FOLDER
        staging.mkdir()
        sub = staging / "data"
        sub.mkdir()
        (sub / "f.txt").write_text("x")

        # Need to create parent for restore target
        (tmp_path / "data2").mkdir(exist_ok=True)

        restore_staged_files(str(staging))
        assert not staging.exists()


# ---------------------------------------------------------------------------
# Integration: full flow
# ---------------------------------------------------------------------------

class TestFullStagingFlow:
    """End-to-end test of the staging workflow."""

    def test_stage_review_delete_flow(self, tmp_path):
        staging = tmp_path / STAGING_FOLDER

        # Create duplicate files
        originals = []
        for name in ["file1.txt", "file2.txt", "file3.txt"]:
            f = tmp_path / "docs" / name
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("same content")
            originals.append(str(f))

        # Step 1: Auto-stage (keep newest)
        duplicates = [make_dup_group(originals)]
        stage_result = auto_stage_duplicates(duplicates, str(staging))

        assert len(stage_result["kept"]) == 1
        assert len(stage_result["staged"]) == 2

        # Step 2: Review staged files
        staged = list_staged_files(str(staging))
        assert len(staged) == 2

        # Step 3: Confirm deletion
        delete_result = confirm_delete_staged(str(staging))
        assert delete_result["deleted_count"] == 2

        # Only keeper remains
        keeper = Path(stage_result["kept"][0])
        assert keeper.exists()

    def test_stage_review_restore_flow(self, tmp_path):
        staging = tmp_path / STAGING_FOLDER

        originals = []
        for name in ["a.txt", "b.txt"]:
            f = tmp_path / "data" / name
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("dup")
            originals.append(str(f))

        # Stage
        duplicates = [make_dup_group(originals)]
        auto_stage_duplicates(duplicates, str(staging))

        # Restore instead of delete
        result = restore_staged_files(str(staging))
        assert result["restored_count"] >= 1

        # Both files should be back (keeper never moved, other restored)
        for p in originals:
            # Keeper was never moved; restored one is back
            assert Path(p).exists() or Path(stage_result["kept"][0]) == Path(p)


# ---------------------------------------------------------------------------
# CLI smoke tests
# ---------------------------------------------------------------------------

class TestCleanupCLI:
    """Smoke tests for the cleanup CLI."""

    def test_cleanup_help(self):
        from typer.testing import CliRunner
        from scripts.cleanup import app

        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "staged" in result.output.lower() or "deletion" in result.output.lower()

    def test_duplicates_auto_stage_help(self):
        from typer.testing import CliRunner
        from scripts.find_duplicates import app

        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "--auto-stage" in result.output
        assert "--dry-run" in result.output

    def test_unified_cli_cleanup_help(self):
        from typer.testing import CliRunner
        from scripts.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["cleanup", "--help"])
        assert result.exit_code == 0
        assert "--confirm" in result.output
        assert "--restore" in result.output
