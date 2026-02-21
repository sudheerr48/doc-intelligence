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
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich.rule import Rule

from src.scanner import scan_folder_incremental, NUM_WORKERS, _collect_files_with_stats
from src.storage import FileDatabase
from src.utils import load_config, format_size


console = Console()

app = typer.Typer(help="Scan folders and build the file index.")


def _metric_card(label: str, value: str, style: str = "bold green") -> Panel:
    content = Text(value, style=style, justify="center")
    return Panel(content, title=f"[dim]{label}[/dim]", border_style="bright_black",
                 width=20, padding=(0, 1))


def run_scan(
    config_path: Optional[str] = None,
    path: Optional[str] = None,
    category: str = "cli",
    algorithm: Optional[str] = None,
):
    """Core scan logic used by both Typer CLI and legacy main()."""
    start_time = time.time()

    console.print()
    console.print(Panel(
        "[bold white]Doc Intelligence[/bold white] [dim]v4.0[/dim]  [bold cyan]Scanner[/bold cyan]\n"
        f"[dim]{NUM_WORKERS} workers | Incremental mode[/dim]",
        border_style="blue",
        padding=(0, 2),
    ))
    console.print()

    # Load config
    config = load_config(config_path)

    # Initialize database
    db_path = Path(config["database"]["path"]).expanduser()

    db = FileDatabase(str(db_path))

    # Get scan settings
    include_ext = config.get("include_extensions", [])
    exclude_patterns = config.get("exclude_patterns", [])
    min_size = config.get("deduplication", {}).get("min_size_bytes", 1024)
    hash_algo = algorithm or config.get("deduplication", {}).get("hash_algorithm", "xxhash")

    console.print(f"  [dim]Database:[/dim]  {db_path}")
    console.print(f"  [dim]Algorithm:[/dim] {hash_algo}  [dim]Min size:[/dim] {format_size(min_size)}")
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
            console.print(f"  [yellow]Skipping (not found):[/yellow] {folder_path}")
            continue

        console.print(Rule(f"[bold]{folder_path}[/bold]  [dim]({cat})[/dim]", style="bright_black"))

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
            console.print(f"  [green]+{len(result.new_files):,} new/modified[/green] ({format_size(new_size)})  "
                          f"[dim]{result.unchanged_count:,} cached  {result.removed_count:,} removed[/dim]  "
                          f"[dim]{folder_time:.1f}s[/dim]")
        else:
            console.print(f"  [dim]No changes ({result.unchanged_count:,} files cached) {folder_time:.1f}s[/dim]")

        console.print()

        total_new += len(result.new_files)
        total_unchanged += result.unchanged_count
        total_removed += result.removed_count
        total_size += result.total_size

    elapsed = time.time() - start_time

    # Show summary
    db_stats = db.get_stats()

    console.print(Panel("[bold green]Scan Complete[/bold green]", border_style="green"))
    console.print()

    cards = [
        _metric_card("New/Modified", f"{total_new:,}", "bold green"),
        _metric_card("Cached", f"{total_unchanged:,}", "dim"),
        _metric_card("Total in DB", f"{db_stats['total_files']:,}", "bold cyan"),
        _metric_card("Duplicates", f"{db_stats['duplicate_sets']:,}", "bold yellow" if db_stats['duplicate_sets'] else "bold green"),
    ]
    console.print(Columns(cards, equal=True, expand=True))

    console.print()
    console.print(f"  [dim]Total size:[/dim] {format_size(db_stats['total_size_bytes'])}  "
                  f"[dim]Time:[/dim] {elapsed:.1f}s  "
                  f"[dim]Database:[/dim] {db_path}")

    # Show by category
    if db_stats["by_category"]:
        console.print()
        console.print(Rule("[bold]By Category[/bold]", style="bright_black"))
        max_val = max(db_stats["by_category"].values()) or 1
        for cat_name, count in db_stats["by_category"].items():
            bar_len = int((count / max_val) * 30)
            bar = "[cyan]" + "\u2501" * bar_len + "[/cyan]"
            console.print(f"  {cat_name:<20} {bar} [dim]{count:,}[/dim]")

    console.print()
    console.print("[dim]Next: doc-intelligence duplicates | doc-intelligence stats | doc-intelligence health[/dim]\n")

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
