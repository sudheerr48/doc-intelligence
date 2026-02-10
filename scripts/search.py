#!/usr/bin/env python3
"""
Search Script
Search for files in the database.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from rich.console import Console
from rich.table import Table

from src.storage import FileDatabase


console = Console()


def load_config(config_path: str = None) -> dict:
    """Load configuration from YAML file."""
    if config_path is None:
        config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    
    with open(config_path) as f:
        return yaml.safe_load(f)


def format_size(size_bytes: int) -> str:
    """Format bytes to human readable size."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def main():
    """Main search function."""
    if len(sys.argv) < 2:
        console.print("\n[bold]Usage:[/bold] python scripts/search.py <query>")
        console.print("\n[bold]Examples:[/bold]")
        console.print("  python scripts/search.py I-140")
        console.print("  python scripts/search.py tax 2023")
        console.print("  python scripts/search.py passport")
        return
    
    query = " ".join(sys.argv[1:])
    
    console.print(f"\n[bold blue]🔍 Searching for: '{query}'[/bold blue]\n")
    
    # Load config
    config = load_config()
    
    # Connect to database
    db_path = Path(config["database"]["path"]).expanduser()
    
    if not db_path.exists():
        console.print("[red]❌ Database not found. Run 'python scripts/scan.py' first.[/red]")
        return
    
    db = FileDatabase(str(db_path))
    
    # Search
    results = db.search(query, limit=50)
    
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
    
    if len(results) == 50:
        console.print("\n[dim]Showing first 50 results. Refine your search for more specific results.[/dim]")
    
    db.close()


if __name__ == "__main__":
    main()

