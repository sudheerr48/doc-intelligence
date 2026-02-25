#!/usr/bin/env python3
"""
Unified CLI Entry Point
Provides a single command with subcommands for file intelligence.

Running with no subcommand launches interactive mode.

Usage:
    doc-intelligence                   # Interactive mode
    doc-intelligence scan [OPTIONS]
    doc-intelligence duplicates [OPTIONS]
    doc-intelligence search QUERY [OPTIONS]
    doc-intelligence stats [OPTIONS]
    doc-intelligence big-files [OPTIONS]
    doc-intelligence report [OPTIONS]
    doc-intelligence similar-images [OPTIONS]
    doc-intelligence history [OPTIONS]
    doc-intelligence dashboard [OPTIONS]
    doc-intelligence tag [OPTIONS]      # AI-powered file tagging
    doc-intelligence tags [TAG]         # Browse tags
    doc-intelligence ask QUERY          # Natural language queries
    doc-intelligence health [OPTIONS]   # File system health report
    doc-intelligence embed [OPTIONS]    # Generate embeddings for semantic search
    doc-intelligence semantic-search Q  # Search files by meaning
    doc-intelligence serve [OPTIONS]    # Start MCP server for AI assistants
"""

import json
import sys
import subprocess
from pathlib import Path
from typing import Optional

# Add src to path for direct script execution
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, MofNCompleteColumn
from rich.rule import Rule

from src.core.database import FileDatabase
from src.core.config import load_config, format_size

console = Console()

# ---------------------------------------------------------------------------
# Shared UI helpers
# ---------------------------------------------------------------------------

_BRAND = "Doc Intelligence"
_TAGLINE = "Your files, understood."
_VERSION = "5.0"


def _header(subtitle: str = ""):
    """Print a branded header."""
    title = f"[bold white]{_BRAND}[/bold white] [dim]v{_VERSION}[/dim]"
    if subtitle:
        title += f"  [bold cyan]{subtitle}[/bold cyan]"
    console.print(Panel(title, border_style="blue", padding=(0, 2)))
    console.print()


def _metric_card(label: str, value: str, style: str = "bold green") -> Panel:
    """Build a single metric card for dashboard-style layouts."""
    content = Text(value, style=style, justify="center")
    return Panel(content, title=f"[dim]{label}[/dim]", border_style="bright_black",
                 width=20, padding=(0, 1))


def _metric_row(metrics: list[tuple[str, str, str]]):
    """Print a row of metric cards. Each tuple is (label, value, style)."""
    cards = [_metric_card(label, value, style) for label, value, style in metrics]
    console.print(Columns(cards, equal=True, expand=True))
    console.print()


def _bar_chart(items: list[tuple[str, int]], max_width: int = 30, color: str = "cyan"):
    """Print a simple horizontal bar chart."""
    if not items:
        return
    max_val = max(v for _, v in items) or 1
    for label, value in items:
        bar_len = int((value / max_val) * max_width)
        bar = "[{c}]{bar}[/{c}]".format(c=color, bar="━" * bar_len + ("╸" if bar_len < max_width else ""))
        console.print(f"  {label:<20} {bar} [dim]{value:,}[/dim]")


def _open_db(config_path: Optional[str] = None) -> tuple[dict, Optional[FileDatabase]]:
    """Load config and open DB, or print error and return None."""
    cfg = load_config(config_path)
    db_path = Path(cfg["database"]["path"]).expanduser()
    if not db_path.exists():
        console.print(Panel(
            "[bold red]Database not found[/bold red]\n\n"
            "Run [bold cyan]doc-intelligence scan[/bold cyan] first to index your files.",
            border_style="red", title="Error",
        ))
        return cfg, None
    return cfg, FileDatabase(str(db_path))


def _truncate_path(p: str, max_len: int = 50) -> str:
    """Truncate a path for display."""
    if len(p) <= max_len:
        return p
    return "..." + p[-(max_len - 3):]


def _similarity_bar(score: float) -> str:
    """Render a mini similarity bar."""
    filled = int(score * 10)
    return "[green]" + "█" * filled + "[/green][bright_black]" + "░" * (10 - filled) + "[/bright_black]"


def _severity_icon(sev: str) -> str:
    """Return a colored icon for issue severity."""
    return {"high": "[red]●[/red]", "medium": "[yellow]●[/yellow]", "low": "[blue]●[/blue]"}.get(
        sev, "[dim]●[/dim]"
    )


# ---------------------------------------------------------------------------
# App definition
# ---------------------------------------------------------------------------

_ASCII_LOGO = r"""
  ____              ___       _       _ _
 |  _ \  ___   ___ |_ _|_ __ | |_ ___| | |
 | | | |/ _ \ / __| | || '_ \| __/ _ \ | |
 | |_| | (_) | (__ | || | | | ||  __/ | |
 |____/ \___/ \___|___|_| |_|\__\___|_|_|
"""

app = typer.Typer(
    name="doc-intelligence",
    help=f"{_BRAND} v{_VERSION} — {_TAGLINE}\n\n"
         "AI-powered file intelligence. Persistent indexing, smart tagging,\n"
         "PII detection, natural language queries, and health reports.\n\n"
         "100% local & private. Your files never leave your machine.\n\n"
         "Run with no subcommand for interactive mode.",
    invoke_without_command=True,
)


@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context):
    """Launch interactive mode when no subcommand is given."""
    if ctx.invoked_subcommand is None:
        from src.interactive import run_interactive
        run_interactive()


# ---------------------------------------------------------------------------
# scan
# ---------------------------------------------------------------------------

@app.command()
def scan(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config YAML file"),
    path: Optional[str] = typer.Option(None, "--path", "-p", help="Scan a single directory instead of config folders"),
    category: str = typer.Option("cli", "--category", help="Category label when using --path"),
    algorithm: Optional[str] = typer.Option(None, "--algorithm", "-a", help="Hash algorithm: xxhash, sha256, md5"),
):
    """Scan folders and build the file index."""
    from scripts.scan import run_scan
    run_scan(config_path=config, path=path, category=category, algorithm=algorithm)


# ---------------------------------------------------------------------------
# duplicates
# ---------------------------------------------------------------------------

@app.command()
def duplicates(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config YAML file"),
    min_size: Optional[int] = typer.Option(None, "--min-size", "-m", help="Minimum file size in bytes to consider"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum number of duplicate sets to display"),
    export_csv: Optional[str] = typer.Option(None, "--export-csv", "-e", help="Export duplicates to CSV file"),
    auto_stage: bool = typer.Option(False, "--auto-stage", help="Automatically stage duplicates for deletion (keeps newest)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview staging without actually moving files"),
    staging_dir: Optional[str] = typer.Option(None, "--staging-dir", help="Custom staging directory path"),
):
    """Find and report duplicate files."""
    from scripts.find_duplicates import run_duplicates
    run_duplicates(
        config_path=config, min_size=min_size, limit=limit,
        export_csv=export_csv, auto_stage=auto_stage, dry_run=dry_run,
        staging_dir=staging_dir,
    )


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

@app.command()
def search(
    query: str = typer.Argument(..., help="Search query (file name or path)"),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config YAML file"),
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum number of results"),
    extension: Optional[str] = typer.Option(None, "--extension", "-x", help="Filter by file extension (e.g. pdf, .txt)"),
):
    """Search for files in the database."""
    from scripts.search import run_search
    run_search(query=query, config_path=config, limit=limit, extension=extension)


# ---------------------------------------------------------------------------
# cleanup
# ---------------------------------------------------------------------------

@app.command()
def cleanup(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config YAML file"),
    confirm: bool = typer.Option(False, "--confirm", help="Permanently delete staged files"),
    restore: bool = typer.Option(False, "--restore", help="Restore staged files to original locations"),
    staging_dir: Optional[str] = typer.Option(None, "--staging-dir", help="Custom staging directory path"),
):
    """Review and manage files staged for deletion."""
    from scripts.cleanup import run_cleanup
    run_cleanup(config_path=config, confirm=confirm, restore=restore, staging_dir=staging_dir)


# ---------------------------------------------------------------------------
# watch
# ---------------------------------------------------------------------------

@app.command()
def watch(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config YAML file"),
    path: Optional[str] = typer.Option(None, "--path", "-p", help="Watch a specific directory"),
    category: str = typer.Option("watched", "--category", help="Category label for watched files"),
):
    """Watch directories for file changes and update the index."""
    from scripts.watch import run_watch
    run_watch(config_path=config, path=path, category=category)


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

@app.command()
def stats(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config YAML file"),
):
    """Show database statistics and disk savings summary."""
    cfg, db = _open_db(config)
    if db is None:
        return
    db_stats = db.get_stats()

    _header("Statistics")

    # Top-level metrics
    duplicates_data = db.get_duplicates()
    total_wasted = sum(d["wasted_size"] for d in duplicates_data)
    dup_files = sum(d["count"] for d in duplicates_data)

    _metric_row([
        ("Total Files", f"{db_stats['total_files']:,}", "bold green"),
        ("Total Size", format_size(db_stats['total_size_bytes']), "bold cyan"),
        ("Duplicates", f"{dup_files:,}", "bold yellow" if dup_files else "bold green"),
        ("Reclaimable", format_size(total_wasted), "bold red" if total_wasted else "bold green"),
    ])

    # Category breakdown with bar chart
    if db_stats["by_category"]:
        console.print(Rule("[bold]Storage by Category[/bold]", style="bright_black"))
        cat_items = sorted(db_stats["by_category"].items(), key=lambda x: x[1], reverse=True)
        _bar_chart(cat_items, color="cyan")
        console.print()

    # Extension breakdown with bar chart
    if db_stats["by_extension"]:
        console.print(Rule("[bold]Top File Types[/bold]", style="bright_black"))
        ext_items = [(ext or "(none)", count) for ext, count in list(db_stats["by_extension"].items())[:15]]
        _bar_chart(ext_items, color="magenta")
        console.print()

    console.print(f"[dim]Database: {Path(cfg['database']['path']).expanduser()}[/dim]\n")
    db.close()


# ---------------------------------------------------------------------------
# big-files
# ---------------------------------------------------------------------------

@app.command("big-files")
def big_files(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config YAML file"),
    top: int = typer.Option(20, "--top", "-n", help="Number of files to show"),
    extension: Optional[str] = typer.Option(None, "--extension", "-x", help="Filter by extension"),
    category: Optional[str] = typer.Option(None, "--category", help="Filter by category"),
):
    """Find the largest files in the database."""
    from scripts.big_files import run_big_files
    run_big_files(config_path=config, top_n=top, extension=extension, category=category)


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

@app.command()
def report(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config YAML file"),
    output: str = typer.Option("doc_intelligence_report.html", "--output", "-o", help="Output file path"),
):
    """Generate a visual HTML report of your file index."""
    from scripts.report import run_report
    run_report(config_path=config, output_path=output)


# ---------------------------------------------------------------------------
# similar-images
# ---------------------------------------------------------------------------

@app.command("similar-images")
def similar_images(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config YAML file"),
    threshold: int = typer.Option(10, "--threshold", "-t", help="Similarity threshold (0=identical, lower=stricter)"),
    limit: int = typer.Option(20, "--limit", "-l", help="Max groups to display"),
):
    """Find visually similar images using perceptual hashing."""
    cfg, db = _open_db(config)
    if db is None:
        return

    try:
        from src.analysis.image_dedup import find_similar_images_from_db
    except ImportError:
        console.print("[red]Image dedup requires: pip install 'doc-intelligence\\[images]'[/red]")
        db.close()
        return

    _header("Similar Images")

    with console.status("[cyan]Scanning for similar images...", spinner="dots"):
        groups = find_similar_images_from_db(db, threshold=threshold)

    if not groups:
        console.print(Panel("[bold green]No similar images found.[/bold green]", border_style="green"))
        db.close()
        return

    total_wasted = sum(g["wasted_size"] for g in groups)
    _metric_row([
        ("Groups Found", str(len(groups)), "bold yellow"),
        ("Reclaimable", format_size(total_wasted), "bold red"),
    ])

    table = Table(border_style="bright_black", show_lines=True, pad_edge=False)
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Copies", style="bold cyan", width=7, justify="center")
    table.add_column("Wasted", style="bold red", width=12, justify="right")
    table.add_column("Files", style="white")

    for i, group in enumerate(groups[:limit], 1):
        paths = group["paths"]
        if len(paths) > 3:
            display = "\n".join(_truncate_path(p, 60) for p in paths[:3]) + f"\n[dim]+ {len(paths) - 3} more[/dim]"
        else:
            display = "\n".join(_truncate_path(p, 60) for p in paths)
        table.add_row(str(i), str(group["count"]), format_size(group["wasted_size"]), display)

    console.print(table)
    console.print()
    db.close()


# ---------------------------------------------------------------------------
# history
# ---------------------------------------------------------------------------

@app.command()
def history(
    days: int = typer.Option(30, "--days", "-d", help="Show deletions from last N days"),
    purge: bool = typer.Option(False, "--purge", help="Remove expired entries from manifest"),
):
    """View deletion history and undo information."""
    from src.undo import get_recent_deletions, purge_expired, get_deletion_summary

    if purge:
        removed = purge_expired()
        console.print(Panel(f"[green]Purged {removed} expired entries.[/green]", border_style="green"))
        return

    _header("Deletion History")

    summary = get_deletion_summary()
    _metric_row([
        ("Total Deleted", f"{summary['total_deleted']:,}", "bold white"),
        ("Bytes Freed", format_size(summary['total_bytes']), "bold cyan"),
        ("Undoable", f"{summary['recent_count']:,}", "bold green"),
        ("Expired", f"{summary['expired_count']:,}", "dim"),
    ])

    recent = get_recent_deletions(days=days)
    if not recent:
        console.print("[dim]No recent deletions.[/dim]\n")
        return

    table = Table(title=f"Last {days} Days", border_style="bright_black", show_lines=False)
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("File", style="cyan")
    table.add_column("Size", style="green", width=10, justify="right")
    table.add_column("Reason", style="yellow", width=18)
    table.add_column("Deleted At", style="dim", width=20)

    for i, entry in enumerate(recent[:50], 1):
        name = Path(entry["original_path"]).name
        table.add_row(
            str(i), name,
            format_size(entry.get("size_bytes", 0)),
            entry.get("reason", "-"),
            entry.get("deleted_at", "-")[:19],
        )

    if len(recent) > 50:
        table.add_row("", f"[dim]... and {len(recent) - 50} more[/dim]", "", "", "")

    console.print(table)
    console.print()


# ---------------------------------------------------------------------------
# tag
# ---------------------------------------------------------------------------

@app.command()
def tag(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config YAML file"),
    limit: int = typer.Option(100, "--limit", "-l", help="Max files to tag per run"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="LLM model to use (default depends on provider)"),
    retag: bool = typer.Option(False, "--retag", help="Re-tag files that already have tags"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="AI provider: anthropic or openai (auto-detected by default)"),
):
    """AI-classify files and assign tags (requires ANTHROPIC_API_KEY or OPENAI_API_KEY)."""
    try:
        from src.ai import classify_batch, is_ai_available, set_provider, get_provider
    except ImportError:
        console.print("[red]AI features require: pip install 'doc-intelligence\\[ai]' or 'doc-intelligence\\[openai]'[/red]")
        return

    if provider:
        set_provider(provider)

    if not is_ai_available():
        console.print(Panel(
            "[bold red]No AI provider configured[/bold red]\n\n"
            "Set one of these environment variables (or add to .env):\n"
            "  [cyan]ANTHROPIC_API_KEY[/cyan]  https://console.anthropic.com/settings/keys\n"
            "  [cyan]OPENAI_API_KEY[/cyan]     https://platform.openai.com/api-keys",
            border_style="red", title="Setup Required",
        ))
        return

    cfg, db = _open_db(config)
    if db is None:
        return

    if retag:
        rows = db.conn.execute("""
            SELECT path, name, extension, size_bytes, category, content_text
            FROM files ORDER BY size_bytes DESC LIMIT ?
        """, [limit]).fetchall()
        files = [
            {"path": r[0], "name": r[1], "extension": r[2],
             "size_bytes": r[3], "category": r[4], "content_text": r[5]}
            for r in rows
        ]
    else:
        files = db.get_untagged_files(limit=limit)

    if not files:
        console.print(Panel("[bold green]All files are already tagged.[/bold green]", border_style="green"))
        db.close()
        return

    active_provider = get_provider()
    _header("AI Tagging")
    console.print(f"  Provider: [bold cyan]{active_provider}[/bold cyan]   Files: [bold]{len(files)}[/bold]\n")

    tag_map = {}
    batch_size = 20

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=30),
        MofNCompleteColumn(),
        TextColumn("[dim]{task.fields[status]}[/dim]"),
        console=console,
    ) as progress:
        task = progress.add_task("Classifying files", total=len(files), status="")
        for i in range(0, len(files), batch_size):
            batch = files[i:i + batch_size]
            try:
                batch_result = classify_batch(batch, model=model, batch_size=batch_size)
                tag_map.update(batch_result)
                progress.update(task, advance=len(batch), status=f"{len(tag_map)} tagged")
            except Exception as e:
                progress.update(task, advance=len(batch), status=f"[yellow]error[/yellow]")
                console.print(f"  [yellow]Batch error (skipping): {e}[/yellow]")

    # Save to database
    updated = db.batch_update_tags(tag_map)
    console.print()

    # Show tag summary
    all_tags = db.get_all_tags()
    if all_tags:
        console.print(Rule("[bold]Tag Summary (Top 20)[/bold]", style="bright_black"))
        tag_items = list(all_tags.items())[:20]
        _bar_chart(tag_items, color="cyan")

    console.print()
    console.print(Panel(f"[bold green]Tagged {updated} files successfully.[/bold green]", border_style="green"))
    console.print()
    db.close()


# ---------------------------------------------------------------------------
# ask
# ---------------------------------------------------------------------------

@app.command()
def ask(
    query: str = typer.Argument(..., help="Natural language question about your files"),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config YAML file"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="LLM model to use (default depends on provider)"),
    show_sql: bool = typer.Option(False, "--show-sql", help="Show the generated SQL query"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="AI provider: anthropic or openai (auto-detected by default)"),
):
    """Ask questions about your files in plain English (requires ANTHROPIC_API_KEY or OPENAI_API_KEY)."""
    try:
        from src.ai import nl_to_sql, is_ai_available, set_provider
    except ImportError:
        console.print("[red]AI features require: pip install 'doc-intelligence\\[ai]' or 'doc-intelligence\\[openai]'[/red]")
        return

    if provider:
        set_provider(provider)

    if not is_ai_available():
        console.print("[red]No AI provider configured. Set ANTHROPIC_API_KEY or OPENAI_API_KEY.[/red]")
        return

    cfg, db = _open_db(config)
    if db is None:
        return
    _header("AI Query")
    console.print(f'  [bold]"{query}"[/bold]\n')

    with console.status("[cyan]Interpreting your question...", spinner="dots"):
        try:
            sql = nl_to_sql(query, model=model)
        except Exception as e:
            console.print(f"[red]Failed to generate query: {e}[/red]")
            db.close()
            return

    if show_sql:
        console.print(Panel(sql, title="Generated SQL", border_style="bright_black"))
        console.print()

    try:
        results = db.run_query(sql)
    except (ValueError, RuntimeError) as e:
        console.print(f"[red]{e}[/red]")
        db.close()
        return

    if not results:
        console.print(Panel("[yellow]No results found.[/yellow]", border_style="yellow"))
        db.close()
        return

    # Display results in a table
    table = Table(
        title=f"Results ({len(results)} rows)",
        border_style="bright_black",
        show_lines=False,
        row_styles=["", "dim"],
    )
    columns = list(results[0].keys())

    for col in columns:
        style = "cyan" if col in ("name", "path") else ("green" if "size" in col else "white")
        table.add_column(col, style=style)

    for row in results[:100]:
        values = []
        for col in columns:
            val = row[col]
            if col in ("size_bytes", "total_size", "wasted_size") and isinstance(val, (int, float)):
                values.append(format_size(int(val)))
            elif val is None:
                values.append("[dim]-[/dim]")
            else:
                s = str(val)
                if len(s) > 80:
                    s = s[:77] + "..."
                values.append(s)
        table.add_row(*values)

    console.print(table)
    console.print()
    db.close()


# ---------------------------------------------------------------------------
# health
# ---------------------------------------------------------------------------

@app.command()
def health(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config YAML file"),
    ai_insights: bool = typer.Option(False, "--ai", help="Add AI-powered analysis (requires ANTHROPIC_API_KEY or OPENAI_API_KEY)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Save report to file"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON instead of text"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="AI provider: anthropic or openai"),
):
    """Generate a file system health report with scoring and recommendations."""
    cfg, db = _open_db(config)
    if db is None:
        return
    metrics = db.get_health_metrics()

    from src.analysis.health import compute_health_score, generate_health_text

    health_data = compute_health_score(metrics)

    # Optionally enhance with AI
    if ai_insights:
        try:
            from src.ai import generate_health_insights, is_ai_available, set_provider
            if provider:
                set_provider(provider)
            if is_ai_available():
                with console.status("[cyan]Getting AI health insights...", spinner="dots"):
                    ai_health = generate_health_insights(metrics)
                health_data["ai_score"] = ai_health.get("score", health_data["score"])
                health_data["ai_grade"] = ai_health.get("grade", health_data["grade"])
                health_data["ai_summary"] = ai_health.get("summary", "")
                health_data["issues"].extend(ai_health.get("issues", []))
                health_data["recommendations"].extend(ai_health.get("recommendations", []))
            else:
                console.print("[yellow]AI not available (missing API key or package).[/yellow]")
        except Exception as e:
            console.print(f"[yellow]AI insights failed: {e}[/yellow]")

    if json_output:
        import json as _json
        print(_json.dumps({"metrics": metrics, "health": health_data}, indent=2, default=str))
        db.close()
        if output:
            Path(output).write_text(
                _json.dumps({"metrics": metrics, "health": health_data}, indent=2, default=str)
            )
            console.print(f"\n[green]Report saved to {Path(output).resolve()}[/green]")
        return

    # Rich-formatted health report
    _header("Health Report")

    # Score display
    score = health_data["score"]
    grade = health_data["grade"]
    grade_colors = {"A": "green", "B": "cyan", "C": "yellow", "D": "red", "F": "bold red", "N/A": "dim"}
    grade_color = grade_colors.get(grade, "white")

    score_bar_filled = int(score / 5)  # 0-20
    score_bar = "[green]" + "█" * score_bar_filled + "[/green][bright_black]" + "░" * (20 - score_bar_filled) + "[/bright_black]"

    console.print(Panel(
        f"  Score: [bold]{score}[/bold]/100  {score_bar}  Grade: [{grade_color}][bold]{grade}[/bold][/{grade_color}]\n"
        f"  {health_data['summary']}",
        border_style=grade_color if grade != "N/A" else "bright_black",
        title="Health Score",
    ))
    console.print()

    # Metric cards
    _metric_row([
        ("Total Files", f"{metrics['total_files']:,}", "bold green"),
        ("Total Size", format_size(metrics['total_size']), "bold cyan"),
        ("Duplicates", f"{metrics['duplicate_sets']:,} sets", "bold yellow" if metrics['duplicate_sets'] else "bold green"),
        ("Wasted", format_size(metrics['wasted_by_duplicates']), "bold red" if metrics['wasted_by_duplicates'] else "bold green"),
    ])

    _metric_row([
        ("Stale (1yr+)", f"{metrics['stale_files']:,}", "bold yellow" if metrics['stale_files'] > 50 else "bold white"),
        ("Large (>100MB)", f"{metrics['large_files']:,}", "bold yellow" if metrics['large_files'] > 10 else "bold white"),
        ("Tagged", f"{metrics['tagged_files']:,}", "bold cyan"),
        ("New (7d)", f"{metrics['new_files_7d']:,}", "bold green"),
    ])

    # Category breakdown
    if metrics["category_breakdown"]:
        console.print(Rule("[bold]Storage by Category[/bold]", style="bright_black"))
        cat_items = [(c["category"] or "unknown", c["files"]) for c in metrics["category_breakdown"]]
        _bar_chart(cat_items, color="cyan")
        console.print()

    # Issues
    if health_data["issues"]:
        console.print(Rule("[bold]Issues[/bold]", style="bright_black"))
        for issue in health_data["issues"]:
            icon = _severity_icon(issue["severity"])
            console.print(f"  {icon} [bold]{issue['title']}[/bold]")
            console.print(f"    [dim]{issue['detail']}[/dim]")
        console.print()

    # Largest files
    if metrics["top_large_files"]:
        console.print(Rule("[bold]Largest Files[/bold]", style="bright_black"))
        for i, f in enumerate(metrics["top_large_files"][:5], 1):
            console.print(f"  [dim]{i}.[/dim] [cyan]{f['name']}[/cyan] [bold]{format_size(f['size'])}[/bold]")
        console.print()

    # Recommendations
    console.print(Rule("[bold]Recommendations[/bold]", style="bright_black"))
    for i, rec in enumerate(health_data["recommendations"], 1):
        console.print(f"  [bold cyan]{i}.[/bold cyan] {rec}")
    console.print()

    # AI insights
    if health_data.get("ai_summary"):
        console.print(Panel(
            f"  Score: [bold]{health_data['ai_score']}[/bold]/100  Grade: [bold]{health_data['ai_grade']}[/bold]\n"
            f"  {health_data['ai_summary']}",
            border_style="blue",
            title="AI Analysis",
        ))
        console.print()

    if output:
        out_path = Path(output)
        out_path.write_text(generate_health_text(metrics, health_data))
        console.print(f"[green]Report saved to {out_path.resolve()}[/green]\n")

    db.close()


# ---------------------------------------------------------------------------
# tags
# ---------------------------------------------------------------------------

@app.command()
def tags(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config YAML file"),
    tag_name: Optional[str] = typer.Argument(None, help="Show files for a specific tag"),
    limit: int = typer.Option(50, "--limit", "-l", help="Max files to show"),
):
    """Browse tags and tagged files."""
    cfg, db = _open_db(config)
    if db is None:
        return

    if tag_name:
        files = db.get_files_by_tag(tag_name, limit=limit)
        if not files:
            console.print(f"[yellow]No files found with tag '{tag_name}'.[/yellow]")
            db.close()
            return

        _header(f"Tag: {tag_name}")

        table = Table(
            title=f"{len(files)} files",
            border_style="bright_black",
            show_lines=False,
            row_styles=["", "dim"],
        )
        table.add_column("Name", style="cyan")
        table.add_column("Size", style="green", width=10, justify="right")
        table.add_column("Category", style="yellow", width=14)
        table.add_column("Tags", style="dim")
        table.add_column("Path", style="white")

        for f in files:
            table.add_row(
                f["name"], format_size(f["size_bytes"]),
                f["category"] or "-",
                ", ".join(f["tags"][:3]),
                _truncate_path(f["path"]),
            )
        console.print(table)
    else:
        all_tags = db.get_all_tags()
        if not all_tags:
            console.print("[yellow]No tags found. Run 'doc-intelligence tag' to classify files.[/yellow]")
            db.close()
            return

        _header("Tags")
        console.print(Rule(f"[bold]{len(all_tags)} unique tags[/bold]", style="bright_black"))
        _bar_chart(list(all_tags.items()), color="cyan")
        console.print()
        console.print("[dim]Use: doc-intelligence tags <tag-name>[/dim]\n")

    db.close()


# ---------------------------------------------------------------------------
# embed
# ---------------------------------------------------------------------------

@app.command()
def embed(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config YAML file"),
    limit: int = typer.Option(500, "--limit", "-l", help="Max files to embed per run"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Embedding model (default: auto-detected)"),
):
    """Generate embeddings for semantic search (requires VOYAGE_API_KEY or OPENAI_API_KEY)."""
    try:
        from src.ai import generate_embeddings, is_embedding_available
    except ImportError:
        console.print("[red]Embedding features require: pip install 'doc-intelligence\\[voyage]' or 'doc-intelligence\\[openai]'[/red]")
        return

    if not is_embedding_available():
        console.print(Panel(
            "[bold red]No embedding API key found[/bold red]\n\n"
            "Set one of these environment variables (or add to .env):\n"
            "  [cyan]VOYAGE_API_KEY[/cyan]   Voyage AI (Anthropic partner): pip install voyageai\n"
            "  [cyan]OPENAI_API_KEY[/cyan]   OpenAI embeddings: pip install openai",
            border_style="red", title="Setup Required",
        ))
        return

    cfg, db = _open_db(config)
    if db is None:
        return
    files = db.get_unembedded_files(limit=limit)

    if not files:
        embed_stats = db.get_embedding_stats()
        console.print(Panel(
            f"[bold green]All files with content are already embedded.[/bold green]\n"
            f"  Total: {embed_stats['embedded_files']} / {embed_stats['files_with_content']}",
            border_style="green",
        ))
        db.close()
        return

    _header("Embedding Generation")

    from src.ai.providers import _detect_embedding_provider, DEFAULT_EMBEDDING_MODELS
    try:
        emb_provider = _detect_embedding_provider()
    except RuntimeError:
        emb_provider = "openai"
    embedding_model = model or DEFAULT_EMBEDDING_MODELS.get(emb_provider, "text-embedding-3-small")
    console.print(f"  Provider: [bold cyan]{emb_provider}[/bold cyan]")
    console.print(f"  Model: [bold cyan]{embedding_model}[/bold cyan]   Files: [bold]{len(files)}[/bold]\n")

    # Build text representations
    texts = []
    paths = []
    for f in files:
        parts = [f["name"]]
        if f.get("tags"):
            try:
                tag_list = json.loads(f["tags"]) if isinstance(f["tags"], str) else f["tags"]
                parts.append("Tags: " + ", ".join(tag_list))
            except (json.JSONDecodeError, TypeError):
                pass
        if f.get("content_text"):
            parts.append(f["content_text"][:4000])
        texts.append("\n".join(parts))
        paths.append(f["path"])

    batch_size = 100
    stored = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=30),
        MofNCompleteColumn(),
        TextColumn("[dim]{task.fields[status]}[/dim]"),
        console=console,
    ) as progress:
        task = progress.add_task("Generating embeddings", total=len(texts), status="")
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_paths = paths[i:i + batch_size]
            try:
                vecs = generate_embeddings(batch_texts, model=embedding_model, batch_size=batch_size)
                items = list(zip(batch_paths, vecs))
                stored += db.store_embeddings_batch(items, model=embedding_model)
                progress.update(task, advance=len(batch_texts), status=f"{stored} stored")
            except Exception as e:
                progress.update(task, advance=len(batch_texts), status="[yellow]error[/yellow]")
                console.print(f"  [yellow]Batch error: {e}[/yellow]")

    embed_stats = db.get_embedding_stats()
    console.print()
    console.print(Panel(
        f"[bold green]Embedded {stored} files[/bold green]\n"
        f"  Total: {embed_stats['embedded_files']} / {embed_stats['files_with_content']} files with content",
        border_style="green",
    ))
    console.print()
    db.close()


# ---------------------------------------------------------------------------
# semantic-search
# ---------------------------------------------------------------------------

@app.command("semantic-search")
def semantic_search(
    query: str = typer.Argument(..., help="Natural language query to search by meaning"),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config YAML file"),
    limit: int = typer.Option(20, "--limit", "-l", help="Max results"),
    threshold: float = typer.Option(0.3, "--threshold", "-t", help="Minimum similarity score (0-1)"),
):
    """Search files by meaning using embeddings (requires VOYAGE_API_KEY or OPENAI_API_KEY)."""
    try:
        from src.ai import generate_embeddings, is_embedding_available
    except ImportError:
        console.print("[red]Semantic search requires: pip install 'doc-intelligence\\[voyage]' or 'doc-intelligence\\[openai]'[/red]")
        return

    if not is_embedding_available():
        console.print("[red]Set VOYAGE_API_KEY or OPENAI_API_KEY for semantic search.[/red]")
        return

    cfg, db = _open_db(config)
    if db is None:
        return
    embed_stats = db.get_embedding_stats()

    if embed_stats["embedded_files"] == 0:
        console.print(Panel(
            "[bold yellow]No embeddings found[/bold yellow]\n\n"
            "Run [bold cyan]doc-intelligence embed[/bold cyan] first to generate embeddings.",
            border_style="yellow",
        ))
        db.close()
        return

    _header("Semantic Search")
    console.print(f'  Query: [bold]"{query}"[/bold]')
    console.print(f"  Searching [bold]{embed_stats['embedded_files']}[/bold] embedded files (threshold: {threshold})\n")

    with console.status("[cyan]Computing similarity...", spinner="dots"):
        try:
            query_vec = generate_embeddings([query])[0]
        except Exception as e:
            console.print(f"[red]Failed to generate query embedding: {e}[/red]")
            db.close()
            return

        results = db.semantic_search(query_vec, limit=limit)

    # Filter by threshold
    results = [r for r in results if r["similarity"] >= threshold]

    if not results:
        console.print(Panel("[yellow]No similar files found above the threshold.[/yellow]", border_style="yellow"))
        db.close()
        return

    table = Table(
        title=f"{len(results)} matches",
        border_style="bright_black",
        show_lines=False,
        row_styles=["", "dim"],
    )
    table.add_column("Score", width=14, justify="left")
    table.add_column("Name", style="cyan")
    table.add_column("Size", style="green", width=10, justify="right")
    table.add_column("Tags", style="dim", width=25)
    table.add_column("Path", style="white")

    for r in results:
        tags_str = ""
        if r.get("tags"):
            try:
                tag_list = json.loads(r["tags"]) if isinstance(r["tags"], str) else []
                tags_str = ", ".join(tag_list[:3])
            except (TypeError, json.JSONDecodeError):
                pass

        score_display = f"{_similarity_bar(r['similarity'])} {r['similarity']:.2f}"
        table.add_row(
            score_display,
            r["name"],
            format_size(r["size_bytes"]),
            tags_str,
            _truncate_path(r["path"]),
        )

    console.print(table)
    console.print()
    db.close()


# ---------------------------------------------------------------------------
# serve (MCP server)
# ---------------------------------------------------------------------------

@app.command()
def serve(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config YAML file"),
    transport: str = typer.Option("stdio", "--transport", "-t", help="Transport: stdio or http"),
    port: int = typer.Option(8765, "--port", help="Port for HTTP transport"),
):
    """Start the MCP server for AI assistants (Claude Desktop, VS Code, etc.)."""
    try:
        from src.mcp.server import run_mcp_server
    except ImportError:
        console.print(Panel(
            "[bold red]MCP server requires the 'mcp' package[/bold red]\n\n"
            "Install with: [cyan]pip install 'doc-intelligence\\[mcp]'[/cyan]",
            border_style="red", title="Setup Required",
        ))
        return

    if transport == "stdio":
        # In stdio mode, don't print to stdout (MCP uses it for communication)
        import sys
        sys.stderr.write(
            f"Doc Intelligence MCP Server v{_VERSION}\n"
            f"Transport: {transport}\n"
            "Ready for connections...\n"
        )
    else:
        _header("MCP Server")
        console.print(f"  Transport: [bold cyan]{transport}[/bold cyan]")
        if transport == "http":
            console.print(f"  Port: [bold cyan]{port}[/bold cyan]")
        console.print()
        console.print("[dim]Waiting for MCP client connections...[/dim]\n")

    run_mcp_server(config_path=config, transport=transport, port=port)


# ---------------------------------------------------------------------------
# dashboard
# ---------------------------------------------------------------------------

@app.command()
def dashboard(
    port: int = typer.Option(8501, "--port", help="Port for the dashboard"),
):
    """Launch the Streamlit web dashboard."""
    # Use the new 13-page dashboard in src/dashboard/app.py
    dashboard_script = Path(__file__).parent.parent / "src" / "dashboard" / "app.py"

    if not dashboard_script.exists():
        # Fallback to legacy dashboard
        dashboard_script = Path(__file__).parent / "dashboard.py"

    if not dashboard_script.exists():
        console.print("[red]Dashboard script not found.[/red]")
        return

    _header("Web Dashboard")
    console.print(f"  Starting on port [bold cyan]{port}[/bold cyan]")
    console.print(f"  Open [link=http://localhost:{port}]http://localhost:{port}[/link] in your browser\n")

    try:
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", str(dashboard_script),
             "--server.port", str(port), "--server.headless", "true"],
        )
    except KeyboardInterrupt:
        console.print("\n[dim]Dashboard stopped.[/dim]")
    except FileNotFoundError:
        console.print("[red]Streamlit not found. Install with: pip install 'doc-intelligence\\[dashboard]'[/red]")


# ---------------------------------------------------------------------------
# providers (plugin introspection)
# ---------------------------------------------------------------------------

@app.command("providers")
def providers_cmd(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config YAML file"),
):
    """Show registered providers and current selections."""
    from src.providers.registry import list_all, COMPONENT_TYPES

    cfg = load_config(config)
    prov_config = cfg.get("providers", {})

    _header("Providers")

    table = Table(border_style="bright_black", show_lines=False, pad_edge=True)
    table.add_column("Component", style="bold cyan", width=14)
    table.add_column("Active", style="bold green", width=22)
    table.add_column("Available", style="white")

    all_providers = list_all()
    for component_type in sorted(COMPONENT_TYPES):
        active = prov_config.get(component_type, "builtin")
        available = all_providers.get(component_type, [])
        available_str = ", ".join(
            f"[bold]{n}[/bold]" if n == active else n
            for n in available
        ) or "[dim](none)[/dim]"
        table.add_row(component_type, active, available_str)

    console.print(table)
    console.print()
    console.print("[dim]Edit config.yaml 'providers' section to switch. See PLUGINS.md to add your own.[/dim]\n")


# ---------------------------------------------------------------------------
# pii-scan
# ---------------------------------------------------------------------------

@app.command("pii-scan")
def pii_scan(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config YAML file"),
    limit: int = typer.Option(500, "--limit", "-l", help="Max files to scan"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
):
    """Scan indexed files for PII (SSNs, credit cards, emails, phones)."""
    from src.ai.pii import scan_files_summary

    cfg, db = _open_db(config)
    if db is None:
        return

    _header("PII Scanner")
    console.print(f"  Scanning up to [bold]{limit}[/bold] files for sensitive data...\n")

    with console.status("[cyan]Scanning for PII patterns...", spinner="dots"):
        summary = scan_files_summary(db, limit=limit)

    if json_output:
        print(json.dumps(summary, indent=2, default=str))
        db.close()
        return

    # Display results
    _metric_row([
        ("Files Scanned", f"{summary['files_scanned']:,}", "bold white"),
        ("Files with PII", f"{summary['files_with_pii']:,}",
         "bold red" if summary['files_with_pii'] else "bold green"),
        ("Total Matches", f"{summary['total_matches']:,}",
         "bold yellow" if summary['total_matches'] else "bold green"),
    ])

    risk = summary["risk_breakdown"]
    if any(risk.values()):
        console.print(Rule("[bold]Risk Breakdown[/bold]", style="bright_black"))
        if risk.get("high"):
            console.print(f"  [red]● High Risk[/red]: {risk['high']} files (SSNs, credit cards)")
        if risk.get("medium"):
            console.print(f"  [yellow]● Medium Risk[/yellow]: {risk['medium']} files (emails, phones)")
        if risk.get("low"):
            console.print(f"  [blue]● Low Risk[/blue]: {risk['low']} files (IPs, addresses)")
        console.print()

    if summary["type_counts"]:
        console.print(Rule("[bold]PII Types Found[/bold]", style="bright_black"))
        _bar_chart(
            sorted(summary["type_counts"].items(), key=lambda x: x[1], reverse=True),
            color="red",
        )
        console.print()

    # Show high-risk files
    if summary["high_risk_files"]:
        console.print(Rule("[bold]High Risk Files[/bold]", style="red"))
        for f in summary["high_risk_files"][:10]:
            console.print(f"  [red]●[/red] [cyan]{Path(f['path']).name}[/cyan]  "
                          f"[dim]{_truncate_path(f['path'], 50)}[/dim]")
            for m in f["matches"][:3]:
                console.print(f"    {m['type']}: [dim]{m['value']}[/dim]  (line {m.get('line', '?')})")
        console.print()
    elif summary['files_with_pii'] == 0:
        console.print(Panel(
            "[bold green]No PII detected in your files.[/bold green]",
            border_style="green",
        ))

    console.print()
    db.close()


# ---------------------------------------------------------------------------
# suggest
# ---------------------------------------------------------------------------

@app.command()
def suggest(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config YAML file"),
    limit: int = typer.Option(20, "--limit", "-l", help="Max suggestions"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
):
    """Get smart suggestions for organizing your files."""
    from src.ai.suggestions import suggest_organization

    cfg, db = _open_db(config)
    if db is None:
        return

    _header("Smart Suggestions")

    with console.status("[cyan]Analyzing your file organization...", spinner="dots"):
        suggestions = suggest_organization(db, max_suggestions=limit)

    if json_output:
        print(json.dumps(suggestions, indent=2, default=str))
        db.close()
        return

    if not suggestions:
        console.print(Panel(
            "[bold green]Your files are well organized![/bold green]",
            border_style="green",
        ))
        db.close()
        return

    console.print(f"  Found [bold]{len(suggestions)}[/bold] suggestions:\n")

    for i, s in enumerate(suggestions, 1):
        priority_icon = {
            "high": "[red]●[/red]",
            "medium": "[yellow]●[/yellow]",
            "low": "[blue]●[/blue]",
        }.get(s.get("priority", "low"), "[dim]●[/dim]")

        console.print(f"  {priority_icon} [bold]{i}. {s['title']}[/bold]")
        console.print(f"    {s['description']}")
        console.print(f"    [cyan]→ {s['suggestion']}[/cyan]")
        if s.get("sample_files"):
            for f in s["sample_files"][:3]:
                console.print(f"      [dim]• {f}[/dim]")
        console.print()

    db.close()


# ---------------------------------------------------------------------------
# image-classify
# ---------------------------------------------------------------------------

@app.command("image-classify")
def image_classify(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config YAML file"),
    limit: int = typer.Option(500, "--limit", "-l", help="Max images to classify"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
):
    """Classify images as screenshots, photos, documents, etc."""
    from src.ai.image_classify import image_classification_summary

    cfg, db = _open_db(config)
    if db is None:
        return

    _header("Image Classification")

    with console.status("[cyan]Classifying images...", spinner="dots"):
        summary = image_classification_summary(db, limit=limit)

    if json_output:
        print(json.dumps(summary, indent=2, default=str))
        db.close()
        return

    if summary["total_images"] == 0:
        console.print("[yellow]No images found in the index.[/yellow]")
        db.close()
        return

    console.print(f"  Classified [bold]{summary['total_images']}[/bold] images:\n")

    if summary["categories"]:
        console.print(Rule("[bold]Image Categories[/bold]", style="bright_black"))
        _bar_chart(
            sorted(summary["categories"].items(), key=lambda x: x[1], reverse=True),
            color="magenta",
        )
        console.print()

    db.close()


# ---------------------------------------------------------------------------
# activate (license key)
# ---------------------------------------------------------------------------

@app.command()
def activate(
    key: str = typer.Argument(..., help="License key (e.g. DI-PRO-...)"),
):
    """Activate a Pro or Team license."""
    from src.licensing.keys import store_license
    from src.licensing.tiers import get_tier_display_name, Tier

    _header("License Activation")

    info = store_license(key)
    if info.valid:
        tier_name = get_tier_display_name(Tier(info.tier))
        console.print(Panel(
            f"[bold green]License activated![/bold green]\n\n"
            f"  Tier: [bold cyan]{tier_name}[/bold cyan]\n"
            f"  Expires: {f'in {info.days_remaining} days' if info.days_remaining is not None else 'Never (perpetual)'}",
            border_style="green",
        ))
    else:
        console.print(Panel(
            f"[bold red]Invalid license key[/bold red]\n\n"
            f"  Error: {info.error}\n\n"
            f"  Get a valid key at https://doc-intelligence.dev/pricing",
            border_style="red",
        ))


# ---------------------------------------------------------------------------
# license (show current license status)
# ---------------------------------------------------------------------------

@app.command("license")
def license_cmd():
    """Show current license status."""
    from src.licensing import get_current_tier, validate_license_key, LicenseInfo, TIER_LIMITS
    from src.licensing.keys import load_stored_license
    from src.licensing.tiers import get_tier_display_name, Tier

    _header("License Status")

    tier = get_current_tier()
    tier_name = get_tier_display_name(tier)
    info = load_stored_license()

    console.print(f"  Current tier: [bold cyan]{tier_name}[/bold cyan]")

    if info and info.valid:
        if info.days_remaining is not None:
            console.print(f"  Expires: in {info.days_remaining} days")
        else:
            console.print(f"  Expires: [green]Never (perpetual)[/green]")
    else:
        console.print(f"  [dim]No license key stored (using Free tier)[/dim]")

    console.print()

    limits = TIER_LIMITS[tier]
    table = Table(border_style="bright_black", show_lines=False)
    table.add_column("Feature", style="cyan")
    table.add_column("Available", width=12, justify="center")

    for feature, available in limits.items():
        if feature == "max_files":
            status = f"[bold]{available if available else 'Unlimited'}[/bold]"
        elif available:
            status = "[green]Yes[/green]"
        else:
            status = "[red]No[/red] [dim](Pro)[/dim]"
        table.add_row(feature.replace("_", " ").title(), status)

    console.print(table)
    console.print()

    if tier == Tier.FREE:
        console.print("[dim]Upgrade: doc-intelligence activate <KEY>[/dim]")
        console.print("[dim]Get a key: https://doc-intelligence.dev/pricing[/dim]\n")


# ---------------------------------------------------------------------------
# telemetry
# ---------------------------------------------------------------------------

@app.command("telemetry")
def telemetry_cmd(
    enable: bool = typer.Option(False, "--enable", help="Opt in to anonymous analytics"),
    disable: bool = typer.Option(False, "--disable", help="Opt out and delete collected data"),
    show_stats: bool = typer.Option(False, "--stats", help="Show local telemetry stats"),
):
    """Manage anonymous usage analytics (OFF by default)."""
    from src.telemetry import (
        enable_telemetry, disable_telemetry, is_telemetry_enabled, get_local_stats,
    )

    if enable:
        enable_telemetry()
        console.print(Panel(
            "[bold green]Telemetry enabled[/bold green]\n\n"
            "We collect: feature usage counts, error types, platform info.\n"
            "We NEVER collect: file names, paths, content, or personal data.\n\n"
            "Opt out anytime: [cyan]doc-intelligence telemetry --disable[/cyan]",
            border_style="green",
        ))
        return

    if disable:
        disable_telemetry()
        console.print(Panel(
            "[bold]Telemetry disabled[/bold]\n\n"
            "All collected data has been deleted.",
            border_style="green",
        ))
        return

    status = "[green]Enabled[/green]" if is_telemetry_enabled() else "[dim]Disabled (default)[/dim]"
    console.print(f"  Telemetry: {status}\n")

    if show_stats:
        stats = get_local_stats()
        if stats["total_events"]:
            console.print(f"  Events: {stats['total_events']}")
            console.print(f"  Errors: {stats['errors']}")
            for event, count in sorted(stats["event_counts"].items(), key=lambda x: x[1], reverse=True):
                console.print(f"    {event}: {count}")
        else:
            console.print("  [dim]No events collected yet.[/dim]")
        console.print()


# ---------------------------------------------------------------------------
# setup (first-run onboarding)
# ---------------------------------------------------------------------------

@app.command()
def setup():
    """Run the first-time setup wizard."""
    from src.onboarding.wizard import run_onboarding, first_run_summary, display_first_run_summary

    config = run_onboarding()
    if config is None:
        return

    # Offer to run first scan
    from rich.prompt import Confirm
    if Confirm.ask("\nRun your first scan now?", default=True):
        from scripts.scan import run_scan
        run_scan()

        # Show summary
        cfg, db = _open_db()
        if db:
            summary = first_run_summary(db)
            display_first_run_summary(summary)
            db.close()


# ---------------------------------------------------------------------------
# platform-info
# ---------------------------------------------------------------------------

@app.command("platform-info")
def platform_info():
    """Show platform detection and installation info."""
    from src.core.platform import detect_platform, get_install_instructions

    info = detect_platform()
    instructions = get_install_instructions()

    _header("Platform Info")

    table = Table(show_header=False, border_style="bright_black", box=None, padding=(0, 2))
    table.add_column(style="bold cyan")
    table.add_column()
    table.add_row("OS", f"{info.os} {info.os_version}")
    table.add_row("Architecture", info.arch)
    table.add_row("Python", info.python_version)
    table.add_row("Config Dir", str(info.config_dir))
    table.add_row("Data Dir", str(info.data_dir))
    table.add_row("Cache Dir", str(info.cache_dir))
    console.print(table)

    if instructions.get("notes"):
        console.print()
        for note in instructions["notes"]:
            console.print(f"  [dim]• {note}[/dim]")

    console.print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """Entry point for the unified CLI."""
    # Check for first-run onboarding
    try:
        from src.onboarding.wizard import is_first_run
        if is_first_run() and len(sys.argv) <= 1:
            console.print(f"\n[bold blue]{_ASCII_LOGO}[/bold blue]")
            console.print(f"  [bold]{_BRAND}[/bold] v{_VERSION} — [dim]{_TAGLINE}[/dim]\n")
            console.print("  [yellow]First time? Run [bold]doc-intelligence setup[/bold] to get started.[/yellow]\n")
    except Exception:
        pass

    app()


if __name__ == "__main__":
    main()
