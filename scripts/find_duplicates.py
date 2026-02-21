#!/usr/bin/env python3
"""
Find Duplicates Script
Reports duplicate files from the scanned database.
Supports automatic staging of duplicates for deletion.
"""

import csv
import sys
from pathlib import Path
from typing import Optional

# Add src to path for direct script execution
sys.path.insert(0, str(Path(__file__).parent.parent))

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from src.core.database import FileDatabase
from src.analysis.duplicates import auto_stage_duplicates, STAGING_FOLDER
from src.core.config import load_config, format_size


console = Console()

app = typer.Typer(help="Find and report duplicate files.")


def run_duplicates(
    config_path: Optional[str] = None,
    min_size: Optional[int] = None,
    limit: int = 20,
    export_csv: Optional[str] = None,
    auto_stage: bool = False,
    dry_run: bool = False,
    staging_dir: Optional[str] = None,
):
    """Core duplicate-finding logic used by both Typer CLI and legacy main()."""
    console.print("\n[bold blue]🔍 Doc Intelligence v1.0 - Duplicate Finder[/bold blue]\n")

    # Load config
    config = load_config(config_path)

    # Connect to database
    db_path = Path(config["database"]["path"]).expanduser()

    if not db_path.exists():
        console.print("[red]❌ Database not found. Run 'python scripts/scan.py' first.[/red]")
        return

    db = FileDatabase(str(db_path))

    # Get duplicates
    duplicates = db.get_duplicates()

    if not duplicates:
        console.print("[green]✅ No duplicates found![/green]")
        db.close()
        return

    # Filter by min_size if specified
    if min_size is not None:
        duplicates = [
            d for d in duplicates
            if (d["total_size"] // d["count"]) >= min_size
        ]
        if not duplicates:
            console.print(f"[green]✅ No duplicates found above {format_size(min_size)}.[/green]")
            db.close()
            return

    # Calculate totals
    total_wasted = sum(d["wasted_size"] for d in duplicates)
    total_sets = len(duplicates)
    total_files = sum(d["count"] for d in duplicates)

    # Summary
    console.print(Panel(
        f"[bold]Found {total_sets} duplicate sets ({total_files} files)[/bold]\n"
        f"Potential space savings: [green]{format_size(total_wasted)}[/green]",
        title="Summary"
    ))

    # Show top duplicates by size
    display_count = min(limit, len(duplicates))
    console.print(f"\n[bold]Top {display_count} Duplicates by Size:[/bold]\n")

    table = Table()
    table.add_column("#", style="dim", width=4)
    table.add_column("Copies", style="cyan", width=6)
    table.add_column("Size Each", style="green", width=12)
    table.add_column("Wasted", style="red", width=12)
    table.add_column("Files", style="white")

    for i, dup in enumerate(duplicates[:limit], 1):
        size_each = dup["total_size"] // dup["count"]

        # Show first 2 paths
        paths = dup["paths"]
        if len(paths) > 2:
            paths_display = "\n".join(paths[:2]) + f"\n... and {len(paths) - 2} more"
        else:
            paths_display = "\n".join(paths)

        table.add_row(
            str(i),
            str(dup["count"]),
            format_size(size_each),
            format_size(dup["wasted_size"]),
            paths_display
        )

    console.print(table)

    # Show _backups duplicates specifically
    backup_dups = [
        d for d in duplicates
        if any("_backups" in p for p in d["paths"])
    ]

    if backup_dups:
        backup_wasted = sum(d["wasted_size"] for d in backup_dups)
        console.print(f"\n[yellow]📁 _backups folder duplicates: {len(backup_dups)} sets ({format_size(backup_wasted)} wasted)[/yellow]")
        console.print("[dim]These are likely safe to delete - originals exist in organized_folder[/dim]")

    # Auto-stage duplicates
    if auto_stage or dry_run:
        if staging_dir:
            staging_root = staging_dir
        else:
            staging_root = str(db_path.parent / STAGING_FOLDER)

        mode = "DRY RUN" if dry_run else "AUTO-STAGE"
        console.print(f"\n[bold yellow]🗂️  {mode}: Staging duplicates (keeping newest)...[/bold yellow]")

        result = auto_stage_duplicates(
            duplicates, staging_root, strategy="newest", dry_run=dry_run,
        )

        console.print(f"  Kept: {len(result['kept'])} files")
        console.print(f"  Staged for deletion: {len(result['staged'])} files")
        console.print(f"  Space to free: {format_size(result['total_bytes_freed'])}")

        if result["errors"]:
            console.print(f"  [red]Errors: {len(result['errors'])}[/red]")
            for err in result["errors"][:5]:
                console.print(f"    [red]{err['original']}: {err.get('reason', 'unknown')}[/red]")

        if dry_run:
            console.print("\n[dim]No files were moved. Remove --dry-run to actually stage files.[/dim]")
        else:
            console.print(f"\n[green]Files staged in: {staging_root}[/green]")
            console.print("[dim]Run 'doc-intelligence cleanup' to review and confirm deletion.[/dim]")

    # Export to CSV if requested
    elif export_csv:
        csv_path = Path(export_csv)
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["hash", "copies", "size_each", "wasted_size", "paths"])
            for dup in duplicates:
                size_each = dup["total_size"] // dup["count"]
                writer.writerow([
                    dup["hash"],
                    dup["count"],
                    size_each,
                    dup["wasted_size"],
                    "|".join(dup["paths"])
                ])
        console.print(f"\n[green]✅ Exported {len(duplicates)} duplicate sets to {csv_path}[/green]")
    else:
        # Show options
        console.print("\n[bold]Options:[/bold]")
        console.print("  • Run with [cyan]--auto-stage[/cyan] to stage duplicates for deletion")
        console.print("  • Run with [cyan]--dry-run[/cyan] to preview what would be staged")
        console.print("  • Run 'python scripts/search.py <query>' to search files")
        console.print("  • Use --export-csv to export duplicate report")

    db.close()


@app.callback(invoke_without_command=True)
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
    run_duplicates(
        config_path=config, min_size=min_size, limit=limit,
        export_csv=export_csv, auto_stage=auto_stage, dry_run=dry_run,
        staging_dir=staging_dir,
    )


def main():
    """Legacy entry point for backward compatibility."""
    app()


if __name__ == "__main__":
    main()
