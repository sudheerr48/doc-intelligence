#!/usr/bin/env python3
"""
Unified CLI Entry Point
Provides a single command with subcommands: scan, duplicates, search, stats,
big-files, report, similar-images, history, dashboard.

Running with no subcommand launches interactive mode.

Usage:
    doc-intelligence                   # Interactive mode
    doc-intelligence scan [OPTIONS]
    doc-intelligence duplicates [OPTIONS]
    doc-intelligence search QUERY [OPTIONS]
    doc-intelligence stats [OPTIONS]
    doc-intelligence big-files [OPTIONS]
    doc-intelligence report [OPTIONS]
    doc-intelligence similar-images [OPTIONS]
    doc-intelligence history [OPTIONS]
    doc-intelligence dashboard [OPTIONS]
"""

import sys
import subprocess
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
    help="Doc Intelligence - Fast file indexing and duplicate detection.\n\n"
         "Run with no subcommand for interactive mode.",
    invoke_without_command=True,
)


@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context):
    """Launch interactive mode when no subcommand is given."""
    if ctx.invoked_subcommand is None:
        from src.interactive import run_interactive
        run_interactive()


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
    """Show database statistics and disk savings summary."""
    cfg = load_config(config)

    db_path = Path(cfg["database"]["path"]).expanduser()

    if not db_path.exists():
        console.print("[red]Database not found. Run 'doc-intelligence scan' first.[/red]")
        return

    db = FileDatabase(str(db_path))
    db_stats = db.get_stats()

    console.print("\n[bold blue]Doc Intelligence - Database Statistics[/bold blue]\n")

    # Overview table
    table = Table(title="Overview")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Total Files", f"{db_stats['total_files']:,}")
    table.add_row("Total Size", format_size(db_stats['total_size_bytes']))
    table.add_row("Duplicate Sets", f"{db_stats['duplicate_sets']:,}")
    table.add_row("Database", str(db_path))

    # Disk savings summary
    duplicates_data = db.get_duplicates()
    if duplicates_data:
        total_wasted = sum(d["wasted_size"] for d in duplicates_data)
        dup_files = sum(d["count"] for d in duplicates_data)
        table.add_row("Duplicate Files", f"{dup_files:,}")
        table.add_row("Potential Savings", f"[bold red]{format_size(total_wasted)}[/bold red]")

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


@app.command("big-files")
def big_files(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config YAML file"),
    top: int = typer.Option(20, "--top", "-n", help="Number of files to show"),
    extension: Optional[str] = typer.Option(None, "--extension", "-x", help="Filter by extension"),
    category: Optional[str] = typer.Option(None, "--category", help="Filter by category"),
):
    """Find the largest files in the database."""
    from scripts.big_files import run_big_files
    run_big_files(config_path=config, top_n=top, extension=extension, category=category)


@app.command()
def report(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config YAML file"),
    output: str = typer.Option("doc_intelligence_report.html", "--output", "-o", help="Output file path"),
):
    """Generate a visual HTML report of your file index."""
    from scripts.report import run_report
    run_report(config_path=config, output_path=output)


@app.command("similar-images")
def similar_images(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config YAML file"),
    threshold: int = typer.Option(10, "--threshold", "-t", help="Similarity threshold (0=identical, lower=stricter)"),
    limit: int = typer.Option(20, "--limit", "-l", help="Max groups to display"),
):
    """Find visually similar images using perceptual hashing."""
    cfg = load_config(config)
    db_path = Path(cfg["database"]["path"]).expanduser()

    if not db_path.exists():
        console.print("[red]Database not found. Run 'doc-intelligence scan' first.[/red]")
        return

    try:
        from src.image_dedup import find_similar_images_from_db
    except ImportError:
        console.print("[red]Image dedup requires: pip install 'doc-intelligence[images]'[/red]")
        return

    db = FileDatabase(str(db_path))

    console.print(f"\n[bold blue]Scanning for similar images (threshold={threshold})...[/bold blue]\n")

    groups = find_similar_images_from_db(db, threshold=threshold)

    if not groups:
        console.print("[green]No similar images found![/green]")
        db.close()
        return

    total_wasted = sum(g["wasted_size"] for g in groups)
    console.print(f"Found [bold]{len(groups)}[/bold] groups of similar images")
    console.print(f"Potential savings: [bold green]{format_size(total_wasted)}[/bold green]\n")

    table = Table()
    table.add_column("#", style="dim", width=4)
    table.add_column("Images", style="cyan", width=6)
    table.add_column("Wasted", style="red", width=12)
    table.add_column("Files", style="white")

    for i, group in enumerate(groups[:limit], 1):
        paths = group["paths"]
        if len(paths) > 3:
            display = "\n".join(paths[:3]) + f"\n... and {len(paths) - 3} more"
        else:
            display = "\n".join(paths)

        table.add_row(
            str(i), str(group["count"]),
            format_size(group["wasted_size"]), display,
        )

    console.print(table)
    db.close()


@app.command()
def history(
    days: int = typer.Option(30, "--days", "-d", help="Show deletions from last N days"),
    purge: bool = typer.Option(False, "--purge", help="Remove expired entries from manifest"),
):
    """View deletion history and undo information."""
    from src.undo import get_recent_deletions, purge_expired, get_deletion_summary

    if purge:
        removed = purge_expired()
        console.print(f"[green]Purged {removed} expired entries.[/green]")
        return

    summary = get_deletion_summary()
    console.print(f"\n[bold blue]Deletion History[/bold blue]\n")
    console.print(f"Total deletions recorded: [bold]{summary['total_deleted']:,}[/bold]")
    console.print(f"Total bytes deleted: [bold]{format_size(summary['total_bytes'])}[/bold]")
    console.print(f"Within undo window: [bold]{summary['recent_count']:,}[/bold]")
    console.print(f"Expired: [dim]{summary['expired_count']:,}[/dim]\n")

    recent = get_recent_deletions(days=days)
    if not recent:
        console.print("[dim]No recent deletions.[/dim]")
        return

    table = Table(title=f"Recent Deletions (last {days} days)")
    table.add_column("#", style="dim", width=4)
    table.add_column("File", style="white")
    table.add_column("Size", style="green", width=10)
    table.add_column("Reason", style="yellow", width=18)
    table.add_column("Deleted At", style="dim", width=20)

    for i, entry in enumerate(recent[:50], 1):
        name = Path(entry["original_path"]).name
        table.add_row(
            str(i), name,
            format_size(entry.get("size_bytes", 0)),
            entry.get("reason", "-"),
            entry.get("deleted_at", "-")[:19],
        )

    if len(recent) > 50:
        table.add_row("...", f"... and {len(recent) - 50} more", "", "", "")

    console.print(table)


@app.command()
def dashboard(
    port: int = typer.Option(8501, "--port", help="Port for the dashboard"),
):
    """Launch the Streamlit web dashboard."""
    dashboard_script = Path(__file__).parent / "dashboard.py"

    if not dashboard_script.exists():
        console.print("[red]Dashboard script not found.[/red]")
        return

    console.print(f"[bold blue]Launching Doc Intelligence Dashboard on port {port}...[/bold blue]")
    console.print(f"[dim]Open http://localhost:{port} in your browser[/dim]\n")

    try:
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", str(dashboard_script),
             "--server.port", str(port), "--server.headless", "true"],
        )
    except KeyboardInterrupt:
        console.print("\n[dim]Dashboard stopped.[/dim]")
    except FileNotFoundError:
        console.print("[red]Streamlit not found. Install with: pip install 'doc-intelligence[dashboard]'[/red]")


def main():
    """Entry point for the unified CLI."""
    app()


if __name__ == "__main__":
    main()
