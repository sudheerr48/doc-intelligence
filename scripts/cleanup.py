#!/usr/bin/env python3
"""
Cleanup Script
Reviews files staged for deletion and confirms permanent removal.
"""

import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

import typer
from rich.console import Console
from rich.table import Table

from src.staging import (
    list_staged_files,
    confirm_delete_staged,
    restore_staged_files,
    STAGING_FOLDER,
)
from src.utils import load_config, format_size


console = Console()

app = typer.Typer(help="Review and manage files staged for deletion.")


def run_cleanup(
    config_path: Optional[str] = None,
    confirm: bool = False,
    restore: bool = False,
    staging_dir: Optional[str] = None,
):
    """Core cleanup logic used by Typer CLI and unified CLI."""
    config = load_config(config_path)

    if staging_dir:
        staging_root = staging_dir
    else:
        staging_root = str(
            Path(config["database"]["path"]).expanduser().parent / STAGING_FOLDER
        )

    console.print("\n[bold blue]🧹 Doc Intelligence - Cleanup Manager[/bold blue]\n")
    console.print(f"Staging folder: {staging_root}\n")

    staged = list_staged_files(staging_root)

    if not staged:
        console.print("[green]No files staged for deletion.[/green]")
        return

    total_size = sum(f["size_bytes"] for f in staged)

    # Show staged files
    table = Table(title=f"Staged Files ({len(staged)} files, {format_size(total_size)})")
    table.add_column("#", style="dim", width=4)
    table.add_column("Original Location", style="white")
    table.add_column("Size", style="green", width=10)

    for i, f in enumerate(staged[:50], 1):
        table.add_row(str(i), f["original_path"], format_size(f["size_bytes"]))

    if len(staged) > 50:
        table.add_row("...", f"... and {len(staged) - 50} more", "")

    console.print(table)

    if restore:
        console.print("\n[yellow]Restoring all staged files to original locations...[/yellow]")
        result = restore_staged_files(staging_root)
        console.print(
            f"[green]Restored {result['restored_count']} files.[/green]"
        )
        if result["errors"]:
            for err in result["errors"]:
                console.print(f"[red]  Error: {err['path']}: {err['error']}[/red]")
        return

    if confirm:
        console.print(
            f"\n[red bold]Permanently deleting {len(staged)} files "
            f"({format_size(total_size)})...[/red bold]"
        )
        result = confirm_delete_staged(staging_root)
        console.print(
            f"[green]Deleted {result['deleted_count']} files, "
            f"freed {format_size(result['deleted_bytes'])}.[/green]"
        )
        if result["errors"]:
            for err in result["errors"]:
                console.print(f"[red]  Error: {err['path']}: {err['error']}[/red]")
    else:
        console.print("\n[bold]Actions:[/bold]")
        console.print("  • Run with [cyan]--confirm[/cyan] to permanently delete staged files")
        console.print("  • Run with [cyan]--restore[/cyan] to move files back to original locations")


@app.callback(invoke_without_command=True)
def cleanup(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config YAML file"),
    confirm: bool = typer.Option(False, "--confirm", help="Permanently delete staged files"),
    restore: bool = typer.Option(False, "--restore", help="Restore staged files to original locations"),
    staging_dir: Optional[str] = typer.Option(None, "--staging-dir", help="Custom staging directory path"),
):
    """Review and manage files staged for deletion."""
    run_cleanup(config_path=config, confirm=confirm, restore=restore, staging_dir=staging_dir)


def main():
    """Legacy entry point."""
    app()


if __name__ == "__main__":
    main()
