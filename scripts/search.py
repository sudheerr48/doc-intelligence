#!/usr/bin/env python3
"""
Search Script
Search for files in the database.
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

app = typer.Typer(help="Search for files in the database.")


def run_search(
    query: str,
    config_path: Optional[str] = None,
    limit: int = 50,
    extension: Optional[str] = None,
):
    """Core search logic used by both Typer CLI and legacy main()."""
    console.print(f"\n[bold blue]🔍 Searching for: '{query}'[/bold blue]\n")

    # Load config
    config = load_config(config_path)

    # Connect to database
    db_path = Path(config["database"]["path"]).expanduser()

    if not db_path.exists():
        console.print("[red]❌ Database not found. Run 'python scripts/scan.py' first.[/red]")
        return

    db = FileDatabase(str(db_path))

    # Search
    results = db.search(query, limit=limit)

    # Filter by extension if specified
    if extension:
        ext = extension if extension.startswith(".") else f".{extension}"
        results = [r for r in results if r["extension"] == ext]

    if not results:
        console.print("[yellow]No files found matching your query.[/yellow]")
        db.close()
        return

    # Display results
    table = Table(title=f"Found {len(results)} files")
    table.add_column("#", style="dim", width=4)
    table.add_column("Name", style="cyan")
    table.add_column("Size", style="green", width=10)
    table.add_column("Category", style="magenta", width=12)
    table.add_column("Path", style="dim")

    for i, result in enumerate(results, 1):
        # Shorten path for display
        path = result["path"]
        if len(path) > 60:
            path = "..." + path[-57:]

        table.add_row(
            str(i),
            result["name"],
            format_size(result["size_bytes"]),
            result["category"] or "-",
            path
        )

    console.print(table)

    if len(results) >= limit:
        console.print(f"\n[dim]Showing first {limit} results. Use --limit to see more or refine your search.[/dim]")

    db.close()


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query (file name or path)"),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config YAML file"),
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum number of results"),
    extension: Optional[str] = typer.Option(None, "--extension", "-x", help="Filter by file extension (e.g. pdf, .txt)"),
):
    """Search for files in the database."""
    run_search(query=query, config_path=config, limit=limit, extension=extension)


def main():
    """Legacy entry point for backward compatibility."""
    app()


if __name__ == "__main__":
    main()
