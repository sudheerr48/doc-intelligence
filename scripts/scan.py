#!/usr/bin/env python3
"""
Scan Script - Fully Parallel & Incremental
Main entry point for scanning folders and building the file index.
Supports resumable scanning - safe to interrupt and restart.
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from rich.console import Console
from rich.table import Table

from src.scanner import scan_folder_incremental, NUM_WORKERS, _collect_files_with_stats
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
    """Main scan function with incremental parallel processing."""
    start_time = time.time()
    
    console.print("\n[bold blue]📁 Doc Intelligence v1.0 - Incremental Scanner[/bold blue]")
    console.print(f"[bold cyan]⚡ Parallel Mode: {NUM_WORKERS} workers | Incremental: Yes[/bold cyan]\n")
    
    # Load config
    config = load_config()
    
    # Initialize database
    db_path = Path(config["database"]["path"]).expanduser()
    console.print(f"[dim]Database: {db_path}[/dim]")
    
    db = FileDatabase(str(db_path))
    
    # Get scan settings
    include_ext = config.get("include_extensions", [])
    exclude_patterns = config.get("exclude_patterns", [])
    min_size = config.get("deduplication", {}).get("min_size_bytes", 1024)
    hash_algo = config.get("deduplication", {}).get("hash_algorithm", "xxhash")
    
    console.print(f"[dim]Hash algorithm: {hash_algo}[/dim]")
    console.print(f"[dim]Min file size: {format_size(min_size)}[/dim]")
    console.print()
    
    total_new = 0
    total_unchanged = 0
    total_removed = 0
    total_size = 0
    
    # Scan each folder incrementally
    for folder_config in config["scan_folders"]:
        folder_path = Path(folder_config["path"]).expanduser()
        category = folder_config.get("category", "unknown")
        
        if not folder_path.exists():
            console.print(f"[yellow]⚠️  Skipping (not found): {folder_path}[/yellow]")
            continue
        
        console.print(f"[bold]📂 {folder_path}[/bold]")
        
        folder_start = time.time()
        
        # Get cached files for this category
        with console.status("[cyan]Checking cache...", spinner="dots"):
            # Collect current file paths first to know what to query
            current_files = _collect_files_with_stats(
                str(folder_path), exclude_patterns, 
                include_ext if include_ext else None, min_size
            )
            current_paths = [f[0] for f in current_files]
            
            # Get cached info for these paths
            cached_files = db.get_cached_file_info(current_paths)
        
        # Scan incrementally
        with console.status(f"[cyan]Scanning with {NUM_WORKERS} workers...", spinner="dots"):
            result = scan_folder_incremental(
                root_path=str(folder_path),
                category=category,
                cached_files=cached_files,
                include_extensions=include_ext if include_ext else None,
                exclude_patterns=exclude_patterns,
                min_size_bytes=min_size,
                hash_algorithm=hash_algo,
                num_workers=NUM_WORKERS
            )
        
        folder_time = time.time() - folder_start
        
        # Insert new files into database
        if result.new_files:
            batch_size = 500
            for i in range(0, len(result.new_files), batch_size):
                batch = result.new_files[i:i + batch_size]
                db.insert_batch(batch)
        
        # Remove deleted files from database
        if result.removed_count > 0:
            valid_paths = {f[0] for f in current_files}
            db.remove_missing_files(valid_paths, category)
        
        # Print results
        new_size = sum(f.size_bytes for f in result.new_files)
        
        if result.new_files or result.removed_count:
            console.print(f"   [green]✓ New/Modified: {len(result.new_files):,} ({format_size(new_size)})[/green]")
            console.print(f"   [dim]  Unchanged: {result.unchanged_count:,} | Removed: {result.removed_count:,}[/dim]")
        else:
            console.print(f"   [dim]✓ No changes ({result.unchanged_count:,} files cached)[/dim]")
        
        console.print(f"   [dim]  Time: {folder_time:.1f}s[/dim]\n")
        
        total_new += len(result.new_files)
        total_unchanged += result.unchanged_count
        total_removed += result.removed_count
        total_size += result.total_size
    
    elapsed = time.time() - start_time
    
    # Show summary
    console.print("[bold green]✅ Scan Complete![/bold green]\n")
    
    stats = db.get_stats()
    
    table = Table(title="Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("New/Modified", f"{total_new:,} files")
    table.add_row("Unchanged (cached)", f"{total_unchanged:,} files")
    table.add_row("Removed", f"{total_removed:,} files")
    table.add_row("Total in DB", f"{stats['total_files']:,} files")
    table.add_row("Total Size", format_size(stats['total_size_bytes']))
    table.add_row("Duplicate Sets", f"{stats['duplicate_sets']:,}")
    table.add_row("Total Time", f"{elapsed:.1f}s")
    
    console.print(table)
    
    # Show by category
    if stats["by_category"]:
        console.print("\n[bold]By Category:[/bold]")
        for cat, count in stats["by_category"].items():
            console.print(f"  {cat}: {count:,} files")
    
    console.print(f"\n[dim]Database: {db_path}[/dim]")
    console.print("[dim]Run 'python scripts/find_duplicates.py' to see duplicates[/dim]\n")
    
    db.close()


if __name__ == "__main__":
    main()
