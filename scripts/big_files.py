#!/usr/bin/env python3
"""
Big Files Script
Find the largest files in the database.
"""

import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from src.core.database import FileDatabase
from src.core.config import load_config, format_size

console = Console()

app = typer.Typer(help="Find the largest files in the database.")


def run_big_files(
    config: Optional[dict] = None,
    config_path: Optional[str] = None,
    top_n: int = 20,
    extension: Optional[str] = None,
    category: Optional[str] = None,
):
    """Core big-files logic."""
    if config is None:
        config = load_config(config_path)

    db_path = Path(config["database"]["path"]).expanduser()

    if not db_path.exists():
        console.print("[red]Database not found. Run 'doc-intelligence scan' first.[/red]")
        return

    db = FileDatabase(str(db_path))

    # Build query with optional filters
    conditions = []
    params = []

    if extension:
        ext = extension if extension.startswith(".") else f".{extension}"
        conditions.append("extension = ?")
        params.append(ext)

    if category:
        conditions.append("category = ?")
        params.append(category)

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    params.append(top_n)

    rows = db.conn.execute(f"""
        SELECT path, name, extension, size_bytes, category
        FROM files
        {where_clause}
        ORDER BY size_bytes DESC
        LIMIT ?
    """, params).fetchall()

    if not rows:
        console.print("[yellow]No files found matching your criteria.[/yellow]")
        db.close()
        return

    # Calculate total
    total_size = sum(row[3] for row in rows)

    console.print(Panel(
        f"[bold]Top {len(rows)} largest files[/bold]\n"
        f"Combined size: [bold green]{format_size(total_size)}[/bold green]",
        title="Big Files",
        border_style="blue",
    ))

    table = Table()
    table.add_column("#", style="dim", width=4)
    table.add_column("Name", style="cyan", max_width=40)
    table.add_column("Size", style="green", width=12)
    table.add_column("Type", style="magenta", width=8)
    table.add_column("Category", style="yellow", width=12)
    table.add_column("Path", style="dim")

    for i, row in enumerate(rows, 1):
        path_display = row[0]
        if len(path_display) > 55:
            path_display = "..." + path_display[-52:]

        table.add_row(
            str(i),
            row[1],
            format_size(row[3]),
            row[2] or "-",
            row[4] or "-",
            path_display,
        )

    console.print(table)

    # Show stats context
    stats = db.get_stats()
    if stats["total_size_bytes"] > 0:
        pct = (total_size / stats["total_size_bytes"]) * 100
        console.print(
            f"\nThese {len(rows)} files represent "
            f"[bold]{pct:.1f}%[/bold] of your total indexed storage "
            f"({format_size(stats['total_size_bytes'])})."
        )

    db.close()


@app.callback(invoke_without_command=True)
def big_files(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config YAML file"),
    top: int = typer.Option(20, "--top", "-n", help="Number of files to show"),
    extension: Optional[str] = typer.Option(None, "--extension", "-x", help="Filter by extension"),
    category: Optional[str] = typer.Option(None, "--category", help="Filter by category"),
):
    """Find the largest files in the database."""
    run_big_files(config_path=config, top_n=top, extension=extension, category=category)


def main():
    app()


if __name__ == "__main__":
    main()
