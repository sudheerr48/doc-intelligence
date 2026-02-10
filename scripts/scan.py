#!/usr/bin/env python3
"""
Scan Script - Fully Parallel & Incremental
Main entry point for scanning folders and building the file index.
Supports resumable scanning - safe to interrupt and restart.
"""

import sys
import time
from pathlib import Path
from typing import Optional

# Add src to path for direct script execution
sys.path.insert(0, str(Path(__file__).parent.parent))

import typer
from rich.console import Console
from rich.table import Table

from src.scanner import scan_folder_incremental, NUM_WORKERS, _collect_files_with_stats
from src.storage import FileDatabase
from src.utils import load_config, format_size


console = Console()

app = typer.Typer(help="Scan folders and build the file index.")


def run_scan(
    config_path: Optional[str] = None,
    path: Optional[str] = None,
    category: str = "cli",
    algorithm: Optional[str] = None,
):
    """Core scan logic used by both Typer CLI and legacy main()."""
    start_time = time.time()

    console.print("\n[bold blue]📁 Doc Intelligence v1.0 - Incremental Scanner[/bold blue]")
    console.print(f"[bold cyan]⚡ Parallel Mode: {NUM_WORKERS} workers | Incremental: Yes[/bold cyan]\n")

    # Load config
    config = load_config(config_path)

    # Initialize database
    db_path = Path(config["database"]["path"]).expanduser()
    console.print(f"[dim]Database: {db_path}[/dim]")

    db = FileDatabase(str(db_path))

    # Get scan settings
    include_ext = config.get("include_extensions", [])
    exclude_patterns = config.get("exclude_patterns", [])
    min_size = config.get("deduplication", {}).get("min_size_bytes", 1024)
    hash_algo = algorithm or config.get("deduplication", {}).get("hash_algorithm", "xxhash")

    console.print(f"[dim]Hash algorithm: {hash_algo}[/dim]")
    console.print(f"[dim]Min file size: {format_size(min_size)}[/dim]")
    console.print()

    total_new = 0
    total_unchanged = 0
    total_removed = 0
    total_size = 0

    # Build folder list: CLI --path overrides config
    if path:
        folders = [{"path": path, "category": category}]
    else:
        folders = config["scan_folders"]

    # Scan each folder incrementally
    for folder_config in folders:
        folder_path = Path(folder_config["path"]).expanduser()
        cat = folder_config.get("category", "unknown")

        if not folder_path.exists():
            console.print(f"[yellow]⚠️  Skipping (not found): {folder_path}[/yellow]")
            continue

        console.print(f"[bold]📂 {folder_path}[/bold]")

        folder_start = time.time()

        # Get cached files for this category
        with console.status("[cyan]Checking cache...", spinner="dots"):
            current_files = _collect_files_with_stats(
                str(folder_path), exclude_patterns,
                include_ext if include_ext else None, min_size
            )
            current_paths = [f[0] for f in current_files]
            cached_files = db.get_cached_file_info(current_paths)

        # Scan incrementally
        with console.status(f"[cyan]Scanning with {NUM_WORKERS} workers...", spinner="dots"):
            result = scan_folder_incremental(
                root_path=str(folder_path),
                category=cat,
                cached_files=cached_files,
                include_extensions=include_ext if include_ext else None,
                exclude_patterns=exclude_patterns,
                min_size_bytes=min_size,
                hash_algorithm=hash_algo,
                num_workers=NUM_WORKERS
            )

        folder_time = time.time() - folder_start

        # Insert new files into database
        if result.new_files:
            batch_size = 500
            for i in range(0, len(result.new_files), batch_size):
                batch = result.new_files[i:i + batch_size]
                db.insert_batch(batch)

        # Remove deleted files from database
        if result.removed_count > 0:
            valid_paths = {f[0] for f in current_files}
            db.remove_missing_files(valid_paths, cat)

        # Print results
        new_size = sum(f.size_bytes for f in result.new_files)

        if result.new_files or result.removed_count:
            console.print(f"   [green]✓ New/Modified: {len(result.new_files):,} ({format_size(new_size)})[/green]")
            console.print(f"   [dim]  Unchanged: {result.unchanged_count:,} | Removed: {result.removed_count:,}[/dim]")
        else:
            console.print(f"   [dim]✓ No changes ({result.unchanged_count:,} files cached)[/dim]")

        console.print(f"   [dim]  Time: {folder_time:.1f}s[/dim]\n")

        total_new += len(result.new_files)
        total_unchanged += result.unchanged_count
        total_removed += result.removed_count
        total_size += result.total_size

    elapsed = time.time() - start_time

    # Show summary
    console.print("[bold green]✅ Scan Complete![/bold green]\n")

    stats = db.get_stats()

    table = Table(title="Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("New/Modified", f"{total_new:,} files")
    table.add_row("Unchanged (cached)", f"{total_unchanged:,} files")
    table.add_row("Removed", f"{total_removed:,} files")
    table.add_row("Total in DB", f"{stats['total_files']:,} files")
    table.add_row("Total Size", format_size(stats['total_size_bytes']))
    table.add_row("Duplicate Sets", f"{stats['duplicate_sets']:,}")
    table.add_row("Total Time", f"{elapsed:.1f}s")

    console.print(table)

    # Show by category
    if stats["by_category"]:
        console.print("\n[bold]By Category:[/bold]")
        for cat_name, count in stats["by_category"].items():
            console.print(f"  {cat_name}: {count:,} files")

    console.print(f"\n[dim]Database: {db_path}[/dim]")
    console.print("[dim]Run 'doc-intelligence duplicates' to see duplicates[/dim]\n")

    db.close()


@app.callback(invoke_without_command=True)
def scan(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config YAML file"),
    path: Optional[str] = typer.Option(None, "--path", "-p", help="Scan a single directory instead of config folders"),
    category: str = typer.Option("cli", "--category", help="Category label when using --path"),
    algorithm: Optional[str] = typer.Option(None, "--algorithm", "-a", help="Hash algorithm: xxhash, sha256, md5"),
):
    """Scan folders and build the file index."""
    run_scan(config_path=config, path=path, category=category, algorithm=algorithm)


def main():
    """Legacy entry point for backward compatibility."""
    app()


if __name__ == "__main__":
    main()
