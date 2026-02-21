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
from rich.columns import Columns
from rich.text import Text
from rich.rule import Rule
from rich.prompt import Prompt, Confirm, IntPrompt

from src.core.database import FileDatabase
from src.core.config import load_config, format_size
from src.analysis.duplicates import (
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


def _metric_card(label: str, value: str, style: str = "bold green") -> Panel:
    content = Text(value, style=style, justify="center")
    return Panel(content, title=f"[dim]{label}[/dim]", border_style="bright_black",
                 width=20, padding=(0, 1))


def _print_savings(duplicates: list[dict]):
    """Print disk savings summary for duplicate groups."""
    if not duplicates:
        console.print(Panel(
            "[bold green]No duplicates found -- your files are clean![/bold green]",
            border_style="green",
        ))
        return

    total_wasted = sum(d["wasted_size"] for d in duplicates)
    total_sets = len(duplicates)
    total_files = sum(d["count"] for d in duplicates)

    cards = [
        _metric_card("Duplicate Sets", str(total_sets), "bold yellow"),
        _metric_card("Duplicate Files", f"{total_files:,}", "bold yellow"),
        _metric_card("Reclaimable", format_size(total_wasted), "bold red"),
    ]
    console.print(Columns(cards, equal=True, expand=True))
    console.print()


def run_interactive(config_path: Optional[str] = None):
    """Run the interactive wizard."""
    console.print()
    console.print(Panel(
        "[bold white]Doc Intelligence[/bold white] [dim]v4.0[/dim]\n"
        "[dim]AI-powered file intelligence -- scan, deduplicate, tag, and search.[/dim]",
        border_style="blue",
        padding=(1, 3),
    ))

    config = load_config(config_path)

    # Step 1: Scan or use existing data
    db = _get_db(config)
    has_data = db is not None and db.get_stats()["total_files"] > 0

    if has_data:
        stats = db.get_stats()
        console.print()
        cards = [
            _metric_card("Files Indexed", f"{stats['total_files']:,}", "bold green"),
            _metric_card("Total Size", format_size(stats['total_size_bytes']), "bold cyan"),
            _metric_card("Duplicate Sets", f"{stats['duplicate_sets']:,}", "bold yellow" if stats['duplicate_sets'] else "bold green"),
        ]
        console.print(Columns(cards, equal=True, expand=True))
        console.print()

        console.print(Rule("[bold]What would you like to do?[/bold]", style="bright_black"))
        console.print("  [bold cyan]scan[/bold cyan]        Re-scan folders and update the index")
        console.print("  [bold cyan]duplicates[/bold cyan]  Find and manage duplicate files")
        console.print("  [bold cyan]search[/bold cyan]      Search files by name or content")
        console.print("  [bold cyan]big-files[/bold cyan]   Find the largest files")
        console.print("  [bold cyan]report[/bold cyan]      Generate an HTML report")
        console.print("  [bold cyan]stats[/bold cyan]       View detailed statistics")
        console.print("  [bold cyan]quit[/bold cyan]        Exit")
        console.print()

        action = Prompt.ask(
            "[bold]Choose action[/bold]",
            choices=["scan", "duplicates", "search", "big-files", "report", "stats", "quit"],
            default="duplicates",
        )
    else:
        if db:
            db.close()
        console.print()
        console.print(Panel(
            "[bold yellow]No files indexed yet.[/bold yellow]\n\n"
            "Let's scan your folders to get started.",
            border_style="yellow",
        ))
        action = "scan"

    # Dispatch to the chosen action
    if action == "scan":
        _interactive_scan(config, config_path)
        if Confirm.ask("\nCheck for duplicates now?", default=True):
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
        console.print("\n[dim]Goodbye![/dim]\n")
        return

    if db:
        db.close()

    # Offer to continue
    if Confirm.ask("\nDo something else?", default=False):
        run_interactive(config_path)


def _interactive_scan(config: dict, config_path: Optional[str] = None):
    """Interactive scan flow."""
    from scripts.scan import run_scan

    folders = config.get("scan_folders", [])
    console.print()
    console.print(Rule("[bold]Scan Folders[/bold]", style="bright_black"))

    for i, f in enumerate(folders, 1):
        p = Path(f["path"]).expanduser()
        if p.exists():
            status = "[green]ready[/green]"
        else:
            status = "[red]missing[/red]"
        console.print(f"  [dim]{i}.[/dim] [cyan]{p}[/cyan] ({f.get('category', 'unknown')}) {status}")

    console.print()
    scan_choice = Prompt.ask(
        "Scan all configured folders or a custom path?",
        choices=["all", "custom"],
        default="all",
    )

    if scan_choice == "custom":
        custom_path = Prompt.ask("Enter directory path")
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
    console.print()
    _print_savings(duplicates)

    if not duplicates:
        db.close()
        return

    # Show top duplicates
    limit = min(10, len(duplicates))
    console.print(Rule(f"[bold]Top {limit} Duplicate Sets[/bold]", style="bright_black"))
    console.print()

    table = Table(border_style="bright_black", show_lines=True, pad_edge=False)
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Copies", style="bold cyan", width=7, justify="center")
    table.add_column("Each", style="green", width=12, justify="right")
    table.add_column("Wasted", style="bold red", width=12, justify="right")
    table.add_column("Files", style="white")

    for i, dup in enumerate(duplicates[:limit], 1):
        size_each = dup["total_size"] // dup["count"]
        paths = dup["paths"]
        if len(paths) > 2:
            paths_display = "\n".join(paths[:2]) + f"\n[dim]+ {len(paths) - 2} more[/dim]"
        else:
            paths_display = "\n".join(paths)
        table.add_row(
            str(i), str(dup["count"]),
            format_size(size_each), format_size(dup["wasted_size"]),
            paths_display,
        )

    console.print(table)
    console.print()

    # Ask what to do
    action = Prompt.ask(
        "[bold]Action[/bold]",
        choices=["stage", "preview", "export", "skip"],
        default="preview",
    )

    if action == "preview":
        staging_root = str(
            Path(config["database"]["path"]).expanduser().parent / STAGING_FOLDER
        )
        result = auto_stage_duplicates(duplicates, staging_root, strategy="newest", dry_run=True)
        console.print(Panel(
            f"Would stage [bold]{len(result['staged'])}[/bold] files "
            f"(freeing [bold green]{format_size(result['total_bytes_freed'])}[/bold green])\n"
            f"Would keep [bold]{len(result['kept'])}[/bold] files (newest copy of each)",
            border_style="cyan", title="Preview",
        ))

        if Confirm.ask("\nProceed with staging?", default=False):
            result = auto_stage_duplicates(duplicates, staging_root, strategy="newest", dry_run=False)
            console.print(Panel(
                f"[bold green]Staged {len(result['staged'])} files[/bold green]\n"
                f"Run [bold cyan]doc-intelligence cleanup[/bold cyan] to review and confirm.",
                border_style="green",
            ))

    elif action == "stage":
        strategy = Prompt.ask("Keep which copy?", choices=["newest", "shortest"], default="newest")
        staging_root = str(
            Path(config["database"]["path"]).expanduser().parent / STAGING_FOLDER
        )
        result = auto_stage_duplicates(duplicates, staging_root, strategy=strategy, dry_run=False)
        console.print(Panel(
            f"[bold green]Staged {len(result['staged'])} files[/bold green]\n"
            f"Space to free: [bold]{format_size(result['total_bytes_freed'])}[/bold]",
            border_style="green",
        ))

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
        console.print(Panel(f"[bold green]Exported to {export_path}[/bold green]", border_style="green"))

    db.close()


def _interactive_cleanup(config: dict):
    """Interactive cleanup flow for staged files."""
    staging_root = str(
        Path(config["database"]["path"]).expanduser().parent / STAGING_FOLDER
    )
    staged = list_staged_files(staging_root)

    if not staged:
        console.print(Panel("[bold green]No files staged for deletion.[/bold green]", border_style="green"))
        return

    total_size = sum(f["size_bytes"] for f in staged)
    console.print(Panel(
        f"[bold]{len(staged)}[/bold] files staged ({format_size(total_size)})",
        border_style="yellow", title="Staged for Deletion",
    ))

    action = Prompt.ask(
        "[bold]Action[/bold]",
        choices=["delete", "restore", "skip"],
        default="skip",
    )

    if action == "delete":
        if Confirm.ask(
            f"[red]Permanently delete {len(staged)} files ({format_size(total_size)})?[/red]",
            default=False,
        ):
            result = confirm_delete_staged(staging_root)
            console.print(Panel(
                f"[bold green]Deleted {result['deleted_count']} files[/bold green]\n"
                f"Freed {format_size(result['deleted_bytes'])}",
                border_style="green",
            ))
    elif action == "restore":
        result = restore_staged_files(staging_root)
        console.print(Panel(
            f"[bold green]Restored {result['restored_count']} files.[/bold green]",
            border_style="green",
        ))


def _interactive_search(config: dict):
    """Interactive search flow."""
    from scripts.search import run_search

    query = Prompt.ask("[bold]Search query[/bold]")
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
    console.print(Panel(
        f"[bold green]Report saved to {output}[/bold green]\n"
        "[dim]Open it in your browser to explore.[/dim]",
        border_style="green",
    ))


def _interactive_stats(config: dict):
    """Show stats interactively."""
    db = _get_db(config)
    if not db:
        console.print("[red]No database found. Run a scan first.[/red]")
        return

    stats = db.get_stats()

    console.print()
    cards = [
        _metric_card("Total Files", f"{stats['total_files']:,}", "bold green"),
        _metric_card("Total Size", format_size(stats['total_size_bytes']), "bold cyan"),
        _metric_card("Duplicate Sets", f"{stats['duplicate_sets']:,}", "bold yellow" if stats['duplicate_sets'] else "bold green"),
    ]
    console.print(Columns(cards, equal=True, expand=True))
    console.print()

    if stats["by_category"]:
        console.print(Rule("[bold]By Category[/bold]", style="bright_black"))
        max_val = max(stats["by_category"].values()) or 1
        for cat_name, count in sorted(stats["by_category"].items()):
            bar_len = int((count / max_val) * 30)
            bar = "[cyan]" + "\u2501" * bar_len + "[/cyan]"
            console.print(f"  {cat_name:<20} {bar} [dim]{count:,}[/dim]")
        console.print()

    db.close()
