"""
Interactive Mode Module
Walks users through scan -> review duplicates -> cleanup
without requiring them to memorize CLI flags.
"""

import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt

from src.storage import FileDatabase
from src.utils import load_config, format_size
from src.staging import (
    auto_stage_duplicates,
    list_staged_files,
    confirm_delete_staged,
    restore_staged_files,
    STAGING_FOLDER,
)

console = Console()


def _get_db(config: dict) -> Optional[FileDatabase]:
    """Open the database if it exists, or return None."""
    db_path = Path(config["database"]["path"]).expanduser()
    if not db_path.exists():
        return None
    return FileDatabase(str(db_path))


def _print_savings(duplicates: list[dict]):
    """Print disk savings summary for duplicate groups."""
    if not duplicates:
        console.print("[green]No duplicates found - your files are clean![/green]")
        return

    total_wasted = sum(d["wasted_size"] for d in duplicates)
    total_sets = len(duplicates)
    total_files = sum(d["count"] for d in duplicates)

    console.print(Panel(
        f"[bold]{total_sets} duplicate sets[/bold] containing "
        f"[bold]{total_files} files[/bold]\n"
        f"Cleaning up would free: [bold green]{format_size(total_wasted)}[/bold green]",
        title="Disk Savings Summary",
        border_style="green",
    ))


def run_interactive(config_path: Optional[str] = None):
    """Run the interactive wizard."""
    console.print(Panel(
        "[bold]Doc Intelligence[/bold] - Interactive Mode\n"
        "Walk through scanning, finding duplicates, and cleaning up.",
        border_style="blue",
    ))

    config = load_config(config_path)

    # Step 1: Scan or use existing data
    db = _get_db(config)
    has_data = db is not None and db.get_stats()["total_files"] > 0

    if has_data:
        stats = db.get_stats()
        console.print(f"\nDatabase has [bold]{stats['total_files']:,}[/bold] files "
                      f"([bold]{format_size(stats['total_size_bytes'])}[/bold]).\n")
        action = Prompt.ask(
            "What would you like to do?",
            choices=["scan", "duplicates", "search", "big-files", "report", "stats", "quit"],
            default="duplicates",
        )
    else:
        if db:
            db.close()
        console.print("\n[yellow]No files indexed yet.[/yellow]")
        console.print("Let's scan your folders first.\n")
        action = "scan"

    # Dispatch to the chosen action
    if action == "scan":
        _interactive_scan(config, config_path)
        # After scan, offer to check duplicates
        if Confirm.ask("\nWould you like to check for duplicates now?", default=True):
            _interactive_duplicates(config)
    elif action == "duplicates":
        _interactive_duplicates(config)
    elif action == "search":
        _interactive_search(config)
    elif action == "big-files":
        _interactive_big_files(config)
    elif action == "report":
        _interactive_report(config)
    elif action == "stats":
        _interactive_stats(config)
    elif action == "quit":
        console.print("[dim]Goodbye![/dim]")
        return

    if db:
        db.close()

    # Offer to continue
    if Confirm.ask("\nWould you like to do something else?", default=False):
        run_interactive(config_path)


def _interactive_scan(config: dict, config_path: Optional[str] = None):
    """Interactive scan flow."""
    from scripts.scan import run_scan

    folders = config.get("scan_folders", [])
    console.print("\n[bold]Configured scan folders:[/bold]")
    for i, f in enumerate(folders, 1):
        p = Path(f["path"]).expanduser()
        exists = "[green]exists[/green]" if p.exists() else "[red]missing[/red]"
        console.print(f"  {i}. {p} ({f.get('category', 'unknown')}) - {exists}")

    scan_choice = Prompt.ask(
        "\nScan all configured folders or a custom path?",
        choices=["all", "custom"],
        default="all",
    )

    if scan_choice == "custom":
        custom_path = Prompt.ask("Enter directory path to scan")
        category = Prompt.ask("Category label", default="custom")
        run_scan(config_path=config_path, path=custom_path, category=category)
    else:
        run_scan(config_path=config_path)


def _interactive_duplicates(config: dict):
    """Interactive duplicate review flow."""
    db = _get_db(config)
    if not db:
        console.print("[red]No database found. Run a scan first.[/red]")
        return

    duplicates = db.get_duplicates()
    _print_savings(duplicates)

    if not duplicates:
        db.close()
        return

    # Show top duplicates
    limit = min(10, len(duplicates))
    console.print(f"\n[bold]Top {limit} duplicate sets by wasted space:[/bold]\n")

    table = Table()
    table.add_column("#", style="dim", width=4)
    table.add_column("Copies", style="cyan", width=6)
    table.add_column("Size Each", style="green", width=12)
    table.add_column("Wasted", style="red", width=12)
    table.add_column("Files", style="white")

    for i, dup in enumerate(duplicates[:limit], 1):
        size_each = dup["total_size"] // dup["count"]
        paths = dup["paths"]
        if len(paths) > 2:
            paths_display = "\n".join(paths[:2]) + f"\n... and {len(paths) - 2} more"
        else:
            paths_display = "\n".join(paths)
        table.add_row(
            str(i), str(dup["count"]),
            format_size(size_each), format_size(dup["wasted_size"]),
            paths_display,
        )

    console.print(table)

    # Ask what to do
    action = Prompt.ask(
        "\nWhat would you like to do with duplicates?",
        choices=["stage", "preview", "export", "skip"],
        default="preview",
    )

    if action == "preview":
        # Dry run
        staging_root = str(
            Path(config["database"]["path"]).expanduser().parent / STAGING_FOLDER
        )
        result = auto_stage_duplicates(duplicates, staging_root, strategy="newest", dry_run=True)
        console.print(f"\n[bold]Preview:[/bold] Would stage {len(result['staged'])} files "
                      f"(freeing {format_size(result['total_bytes_freed'])})")
        console.print(f"Would keep {len(result['kept'])} files (newest copy of each)")

        if Confirm.ask("\nProceed with staging these files?", default=False):
            result = auto_stage_duplicates(duplicates, staging_root, strategy="newest", dry_run=False)
            console.print(f"[green]Staged {len(result['staged'])} files to {staging_root}[/green]")
            console.print("[dim]Run 'doc-intelligence cleanup' to review and confirm deletion.[/dim]")

    elif action == "stage":
        strategy = Prompt.ask("Keep which copy?", choices=["newest", "shortest"], default="newest")
        staging_root = str(
            Path(config["database"]["path"]).expanduser().parent / STAGING_FOLDER
        )
        result = auto_stage_duplicates(duplicates, staging_root, strategy=strategy, dry_run=False)
        console.print(f"\n[green]Staged {len(result['staged'])} files[/green]")
        console.print(f"Space to free: [bold green]{format_size(result['total_bytes_freed'])}[/bold green]")

        if Confirm.ask("\nReview staged files now?", default=True):
            _interactive_cleanup(config)

    elif action == "export":
        export_path = Prompt.ask("Export CSV path", default="duplicates_report.csv")
        import csv
        with open(export_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["hash", "copies", "size_each", "wasted_size", "paths"])
            for dup in duplicates:
                size_each = dup["total_size"] // dup["count"]
                writer.writerow([
                    dup["hash"], dup["count"], size_each,
                    dup["wasted_size"], "|".join(dup["paths"]),
                ])
        console.print(f"[green]Exported to {export_path}[/green]")

    db.close()


def _interactive_cleanup(config: dict):
    """Interactive cleanup flow for staged files."""
    staging_root = str(
        Path(config["database"]["path"]).expanduser().parent / STAGING_FOLDER
    )
    staged = list_staged_files(staging_root)

    if not staged:
        console.print("[green]No files staged for deletion.[/green]")
        return

    total_size = sum(f["size_bytes"] for f in staged)
    console.print(f"\n[bold]{len(staged)} files staged[/bold] ({format_size(total_size)})")

    action = Prompt.ask(
        "What would you like to do?",
        choices=["delete", "restore", "skip"],
        default="skip",
    )

    if action == "delete":
        if Confirm.ask(
            f"[red]Permanently delete {len(staged)} files ({format_size(total_size)})?[/red]",
            default=False,
        ):
            result = confirm_delete_staged(staging_root)
            console.print(f"[green]Deleted {result['deleted_count']} files, "
                          f"freed {format_size(result['deleted_bytes'])}[/green]")
    elif action == "restore":
        result = restore_staged_files(staging_root)
        console.print(f"[green]Restored {result['restored_count']} files.[/green]")


def _interactive_search(config: dict):
    """Interactive search flow."""
    from scripts.search import run_search

    query = Prompt.ask("Search query")
    ext = Prompt.ask("Filter by extension (leave blank for all)", default="")
    run_search(query=query, extension=ext if ext else None)


def _interactive_big_files(config: dict):
    """Interactive big files flow."""
    from scripts.big_files import run_big_files

    top_n = IntPrompt.ask("How many files to show?", default=20)
    run_big_files(config=config, top_n=top_n)


def _interactive_report(config: dict):
    """Interactive report generation flow."""
    from scripts.report import run_report

    output = Prompt.ask("Output file path", default="doc_intelligence_report.html")
    run_report(config=config, output_path=output)
    console.print(f"\n[green]Report saved to {output}[/green]")
    console.print("[dim]Open it in your browser to explore.[/dim]")


def _interactive_stats(config: dict):
    """Show stats interactively."""
    db = _get_db(config)
    if not db:
        console.print("[red]No database found. Run a scan first.[/red]")
        return

    stats = db.get_stats()

    table = Table(title="Database Overview")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Total Files", f"{stats['total_files']:,}")
    table.add_row("Total Size", format_size(stats['total_size_bytes']))
    table.add_row("Duplicate Sets", f"{stats['duplicate_sets']:,}")
    console.print(table)

    if stats["by_category"]:
        cat_table = Table(title="By Category")
        cat_table.add_column("Category", style="cyan")
        cat_table.add_column("Files", style="green")
        for cat_name, count in sorted(stats["by_category"].items()):
            cat_table.add_row(cat_name, f"{count:,}")
        console.print(cat_table)

    db.close()
