#!/usr/bin/env python3
"""
File Watcher Script
Monitors configured directories for file changes and updates the database.
"""

import sys
import time
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

import typer
from rich.console import Console
from watchdog.observers import Observer

from src.storage import FileDatabase
from src.watcher import FileChangeHandler
from src.utils import load_config


console = Console()

app = typer.Typer(help="Watch directories for file changes and update the index.")


def run_watch(
    config_path: Optional[str] = None,
    path: Optional[str] = None,
    category: str = "watched",
):
    """Core watch logic used by Typer CLI and unified CLI."""
    console.print("\n[bold blue]👁️  Doc Intelligence - File Watcher[/bold blue]\n")

    config = load_config(config_path)
    db_path = Path(config["database"]["path"]).expanduser()
    db = FileDatabase(str(db_path))

    # Determine paths to watch
    if path:
        watch_paths = [path]
    else:
        watch_paths = [
            folder["path"]
            for folder in config.get("scan_folders", [])
        ]

    if not watch_paths:
        console.print("[red]No paths to watch. Use --path or configure scan_folders in config.[/red]")
        db.close()
        return

    exclude = config.get("exclude_patterns", [])
    min_size = config.get("min_file_size_bytes", 0)
    algorithm = config.get("hash_algorithm", "xxhash")

    def on_event(event_type, filepath):
        console.print(f"  [{event_type}] {filepath}")

    observer = Observer()
    for watch_path in watch_paths:
        resolved = str(Path(watch_path).expanduser().resolve())
        if not Path(resolved).exists():
            console.print(f"[yellow]Skipping non-existent path: {watch_path}[/yellow]")
            continue

        handler = FileChangeHandler(
            db=db,
            category=category,
            exclude_patterns=exclude,
            min_size_bytes=min_size,
            hash_algorithm=algorithm,
            on_event_callback=on_event,
        )
        observer.schedule(handler, resolved, recursive=True)
        console.print(f"  Watching: {resolved}")

    console.print(f"\n[green]Monitoring for changes... (Ctrl+C to stop)[/green]\n")

    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping watcher...[/yellow]")
        observer.stop()

    observer.join()
    db.close()
    console.print("[green]Watcher stopped.[/green]")


@app.callback(invoke_without_command=True)
def watch(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config YAML file"),
    path: Optional[str] = typer.Option(None, "--path", "-p", help="Watch a specific directory"),
    category: str = typer.Option("watched", "--category", help="Category label for watched files"),
):
    """Watch directories for file changes and update the index."""
    run_watch(config_path=config, path=path, category=category)


def main():
    """Entry point."""
    app()


if __name__ == "__main__":
    main()
