"""
First-run onboarding wizard with folder detection and guided setup.
"""

import platform
import sys
from pathlib import Path
from typing import Optional

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

# ------------------------------------------------------------------
# Default folder detection
# ------------------------------------------------------------------

_COMMON_FOLDERS = {
    "Darwin": [
        ("~/Documents", "documents"),
        ("~/Downloads", "downloads"),
        ("~/Desktop", "desktop"),
        ("~/Pictures", "photos"),
        ("~/Music", "music"),
        ("~/Movies", "videos"),
    ],
    "Linux": [
        ("~/Documents", "documents"),
        ("~/Downloads", "downloads"),
        ("~/Desktop", "desktop"),
        ("~/Pictures", "photos"),
        ("~/Music", "music"),
        ("~/Videos", "videos"),
    ],
    "Windows": [
        ("~/Documents", "documents"),
        ("~/Downloads", "downloads"),
        ("~/Desktop", "desktop"),
        ("~/Pictures", "photos"),
        ("~/Music", "music"),
        ("~/Videos", "videos"),
        ("~/OneDrive", "onedrive"),
    ],
}


def detect_default_folders() -> list[dict]:
    """Detect existing common folders for the current OS.

    Returns:
        List of {path, category, exists} dicts.
    """
    os_name = platform.system()
    candidates = _COMMON_FOLDERS.get(os_name, _COMMON_FOLDERS["Linux"])

    folders = []
    for path_str, category in candidates:
        path = Path(path_str).expanduser()
        folders.append({
            "path": str(path),
            "display_path": path_str,
            "category": category,
            "exists": path.is_dir(),
        })

    return folders


def is_first_run() -> bool:
    """Check if this is the first time the user is running doc-intelligence."""
    config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
    marker = Path.home() / ".config" / "doc-intelligence" / ".setup_complete"
    return not marker.exists()


def _mark_setup_complete():
    """Mark onboarding as complete."""
    marker = Path.home() / ".config" / "doc-intelligence" / ".setup_complete"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.touch()


# ------------------------------------------------------------------
# Config generation
# ------------------------------------------------------------------

def generate_config(
    selected_folders: list[dict],
    db_path: str = "./data/files.duckdb",
    staging_path: str = "~/_TO_DELETE",
) -> dict:
    """Generate a config dict from selected folders.

    Args:
        selected_folders: List of {path, category} dicts.
        db_path: Database file path.
        staging_path: Staging folder for deletion candidates.

    Returns:
        Config dict ready to be saved as YAML.
    """
    return {
        "scan_folders": [
            {"path": f["display_path"], "category": f["category"]}
            for f in selected_folders
        ],
        "include_extensions": [],
        "exclude_patterns": [
            ".DS_Store", ".git", "__pycache__", "*.pyc",
            ".venv", "venv", "node_modules", ".next",
            ".cache", "*.egg-info", "dist", "build",
        ],
        "deduplication": {
            "hash_algorithm": "xxhash",
            "min_size_bytes": 1024,
        },
        "database": {"path": db_path},
        "staging": {"path": staging_path},
        "reports": {"output_dir": "./data/reports"},
        "ai": {
            "provider": "auto",
            "batch_size": 20,
            "max_tag_files": 500,
        },
    }


def save_config(config: dict, path: Optional[str] = None) -> Path:
    """Save config dict to YAML file."""
    if path is None:
        config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
    else:
        config_path = Path(path)

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))
    return config_path


# ------------------------------------------------------------------
# First-run summary
# ------------------------------------------------------------------

def first_run_summary(db) -> dict:
    """Generate a summary of what was found during the first scan.

    Args:
        db: FileDatabase instance.

    Returns:
        Summary dict with key metrics.
    """
    stats = db.get_stats()
    duplicates = db.get_duplicates()
    total_wasted = sum(d["wasted_size"] for d in duplicates)

    # Top extensions
    top_ext = sorted(
        stats.get("by_extension", {}).items(),
        key=lambda x: x[1],
        reverse=True,
    )[:10]

    return {
        "total_files": stats["total_files"],
        "total_size": stats["total_size_bytes"],
        "categories": stats.get("by_category", {}),
        "duplicate_sets": stats["duplicate_sets"],
        "wasted_space": total_wasted,
        "top_extensions": top_ext,
    }


def display_first_run_summary(summary: dict):
    """Display the first-run summary with Rich formatting."""
    from src.core.config import format_size

    console.print()
    console.print(Panel.fit(
        "[bold green]Scan Complete![/bold green]\n"
        "Here's what Doc Intelligence found on your system:",
        border_style="green",
    ))
    console.print()

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold cyan")
    table.add_column()

    table.add_row("Total Files", f"{summary['total_files']:,}")
    table.add_row("Total Size", format_size(summary['total_size']))
    table.add_row("Duplicate Sets", f"{summary['duplicate_sets']:,}")
    if summary['wasted_space'] > 0:
        table.add_row(
            "Wasted by Duplicates",
            f"[red]{format_size(summary['wasted_space'])}[/red]",
        )

    console.print(table)

    # Categories
    if summary.get("categories"):
        console.print("\n[bold]Files by Category:[/bold]")
        for cat, count in sorted(
            summary["categories"].items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            console.print(f"  {cat or 'unknown'}: {count:,}")

    # Top extensions
    if summary.get("top_extensions"):
        console.print("\n[bold]Top File Types:[/bold]")
        for ext, count in summary["top_extensions"][:5]:
            console.print(f"  {ext}: {count:,}")

    console.print()
    console.print("[dim]Run 'doc-intelligence duplicates' to manage duplicates[/dim]")
    console.print("[dim]Run 'doc-intelligence search <query>' to search files[/dim]")
    console.print("[dim]Run 'doc-intelligence dashboard' for the web interface[/dim]")


# ------------------------------------------------------------------
# Interactive CLI wizard
# ------------------------------------------------------------------

def run_onboarding() -> Optional[dict]:
    """Run the interactive onboarding wizard.

    Returns:
        Generated config dict, or None if the user cancelled.
    """
    console.print()
    console.print(Panel.fit(
        "[bold blue]Welcome to Doc Intelligence![/bold blue]\n\n"
        "Your files, understood.\n\n"
        "Let's set up your file index. This wizard will:\n"
        "  1. Detect your common folders\n"
        "  2. Let you choose which to scan\n"
        "  3. Run your first scan\n\n"
        "[dim]All processing is local. Your files never leave your machine.[/dim]",
        border_style="blue",
    ))
    console.print()

    # Step 1: Detect folders
    folders = detect_default_folders()
    existing = [f for f in folders if f["exists"]]

    if not existing:
        console.print("[yellow]No common folders detected.[/yellow]")
        custom = Prompt.ask("Enter a folder path to scan")
        custom_path = Path(custom).expanduser()
        if custom_path.is_dir():
            existing = [{
                "path": str(custom_path),
                "display_path": custom,
                "category": custom_path.name.lower(),
                "exists": True,
            }]
        else:
            console.print(f"[red]'{custom}' is not a valid directory.[/red]")
            return None

    # Step 2: Let user pick
    console.print("[bold]Detected folders:[/bold]\n")
    for i, f in enumerate(existing, 1):
        console.print(f"  [cyan]{i}.[/cyan] {f['display_path']}  ({f['category']})")

    console.print()
    include_all = Confirm.ask("Scan all detected folders?", default=True)

    if include_all:
        selected = existing
    else:
        choices = Prompt.ask(
            "Enter folder numbers to scan (comma-separated)",
            default=",".join(str(i) for i in range(1, len(existing) + 1)),
        )
        indices = [int(x.strip()) - 1 for x in choices.split(",") if x.strip().isdigit()]
        selected = [existing[i] for i in indices if 0 <= i < len(existing)]

    if not selected:
        console.print("[red]No folders selected. Aborting setup.[/red]")
        return None

    # Step 3: Generate config
    config = generate_config(selected)
    config_path = save_config(config)
    console.print(f"\n[green]Config saved to {config_path}[/green]")

    _mark_setup_complete()
    return config
