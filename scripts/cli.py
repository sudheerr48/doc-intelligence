#!/usr/bin/env python3
"""
Unified CLI Entry Point
Provides a single command with subcommands: scan, duplicates, search, stats.

Usage:
    doc-intelligence scan [OPTIONS]
    doc-intelligence duplicates [OPTIONS]
    doc-intelligence search QUERY [OPTIONS]
    doc-intelligence stats [OPTIONS]
"""

import sys
from pathlib import Path
from typing import Optional

# Add src to path for direct script execution
sys.path.insert(0, str(Path(__file__).parent.parent))

import typer
from rich.console import Console
from rich.table import Table

from src.storage import FileDatabase
from src.utils import load_config, format_size

console = Console()

app = typer.Typer(
    name="doc-intelligence",
    help="Doc Intelligence - Fast file indexing and duplicate detection.",
    no_args_is_help=True,
)


@app.command()
def scan(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config YAML file"),
    path: Optional[str] = typer.Option(None, "--path", "-p", help="Scan a single directory instead of config folders"),
    category: str = typer.Option("cli", "--category", help="Category label when using --path"),
    algorithm: Optional[str] = typer.Option(None, "--algorithm", "-a", help="Hash algorithm: xxhash, sha256, md5"),
):
    """Scan folders and build the file index."""
    from scripts.scan import run_scan
    run_scan(config_path=config, path=path, category=category, algorithm=algorithm)


@app.command()
def duplicates(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config YAML file"),
    min_size: Optional[int] = typer.Option(None, "--min-size", "-m", help="Minimum file size in bytes to consider"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum number of duplicate sets to display"),
    export_csv: Optional[str] = typer.Option(None, "--export-csv", "-e", help="Export duplicates to CSV file"),
    auto_stage: bool = typer.Option(False, "--auto-stage", help="Automatically stage duplicates for deletion (keeps newest)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview staging without actually moving files"),
    staging_dir: Optional[str] = typer.Option(None, "--staging-dir", help="Custom staging directory path"),
):
    """Find and report duplicate files."""
    from scripts.find_duplicates import run_duplicates
    run_duplicates(
        config_path=config, min_size=min_size, limit=limit,
        export_csv=export_csv, auto_stage=auto_stage, dry_run=dry_run,
        staging_dir=staging_dir,
    )


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query (file name or path)"),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config YAML file"),
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum number of results"),
    extension: Optional[str] = typer.Option(None, "--extension", "-x", help="Filter by file extension (e.g. pdf, .txt)"),
):
    """Search for files in the database."""
    from scripts.search import run_search
    run_search(query=query, config_path=config, limit=limit, extension=extension)


@app.command()
def cleanup(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config YAML file"),
    confirm: bool = typer.Option(False, "--confirm", help="Permanently delete staged files"),
    restore: bool = typer.Option(False, "--restore", help="Restore staged files to original locations"),
    staging_dir: Optional[str] = typer.Option(None, "--staging-dir", help="Custom staging directory path"),
):
    """Review and manage files staged for deletion."""
    from scripts.cleanup import run_cleanup
    run_cleanup(config_path=config, confirm=confirm, restore=restore, staging_dir=staging_dir)


@app.command()
def watch(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config YAML file"),
    path: Optional[str] = typer.Option(None, "--path", "-p", help="Watch a specific directory"),
    category: str = typer.Option("watched", "--category", help="Category label for watched files"),
):
    """Watch directories for file changes and update the index."""
    from scripts.watch import run_watch
    run_watch(config_path=config, path=path, category=category)


@app.command()
def stats(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config YAML file"),
):
    """Show database statistics."""
    cfg = load_config(config)

    db_path = Path(cfg["database"]["path"]).expanduser()

    if not db_path.exists():
        console.print("[red]❌ Database not found. Run 'doc-intelligence scan' first.[/red]")
        return

    db = FileDatabase(str(db_path))
    db_stats = db.get_stats()

    console.print("\n[bold blue]📊 Doc Intelligence - Database Statistics[/bold blue]\n")

    # Overview table
    table = Table(title="Overview")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Total Files", f"{db_stats['total_files']:,}")
    table.add_row("Total Size", format_size(db_stats['total_size_bytes']))
    table.add_row("Duplicate Sets", f"{db_stats['duplicate_sets']:,}")
    table.add_row("Database", str(db_path))

    console.print(table)

    # By category
    if db_stats["by_category"]:
        console.print()
        cat_table = Table(title="By Category")
        cat_table.add_column("Category", style="cyan")
        cat_table.add_column("Files", style="green")

        for cat_name, count in sorted(db_stats["by_category"].items()):
            cat_table.add_row(cat_name, f"{count:,}")

        console.print(cat_table)

    # By extension (top 20)
    if db_stats["by_extension"]:
        console.print()
        ext_table = Table(title="Top Extensions")
        ext_table.add_column("Extension", style="cyan")
        ext_table.add_column("Files", style="green")

        for ext, count in db_stats["by_extension"].items():
            ext_table.add_row(ext or "(none)", f"{count:,}")

        console.print(ext_table)

    console.print()
    db.close()


def main():
    """Entry point for the unified CLI."""
    app()


if __name__ == "__main__":
    main()
