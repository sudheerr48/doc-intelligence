#!/usr/bin/env python3
"""
Find Duplicates Script
Reports duplicate files from the scanned database.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

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
    """Main function to find and report duplicates."""
    console.print("\n[bold blue]🔍 Doc Intelligence v1.0 - Duplicate Finder[/bold blue]\n")
    
    # Load config
    config = load_config()
    
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
    console.print("\n[bold]Top 20 Duplicates by Size:[/bold]\n")
    
    table = Table()
    table.add_column("#", style="dim", width=4)
    table.add_column("Copies", style="cyan", width=6)
    table.add_column("Size Each", style="green", width=12)
    table.add_column("Wasted", style="red", width=12)
    table.add_column("Files", style="white")
    
    for i, dup in enumerate(duplicates[:20], 1):
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
    
    # Export option
    console.print("\n[bold]Options:[/bold]")
    console.print("  • Run 'python scripts/search.py <query>' to search files")
    console.print("  • Review duplicates and move to ~/_TO_DELETE/")
    console.print("  • Delete _backups folder: rm -rf ~/Desktop/Sudheer_AllDocs/organized_folder/_backups/")
    
    db.close()


if __name__ == "__main__":
    main()

