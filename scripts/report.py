#!/usr/bin/env python3
"""
HTML Report Generator
Generates a visual HTML report of storage breakdown, duplicates, and file categories.
"""

import sys
import json
from pathlib import Path
from typing import Optional
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

import typer
from rich.console import Console

from src.core.database import FileDatabase
from src.core.config import load_config, format_size

console = Console()

app = typer.Typer(help="Generate an HTML report of your file index.")


def _get_size_by_extension(db: FileDatabase, limit: int = 15) -> list[dict]:
    """Get total size grouped by extension."""
    rows = db.conn.execute("""
        SELECT extension, COUNT(*) as count, SUM(size_bytes) as total_size
        FROM files
        GROUP BY extension
        ORDER BY total_size DESC
        LIMIT ?
    """, [limit]).fetchall()
    return [{"ext": r[0] or "(no ext)", "count": r[1], "size": r[2]} for r in rows]


def _get_size_by_category(db: FileDatabase) -> list[dict]:
    """Get total size grouped by category."""
    rows = db.conn.execute("""
        SELECT category, COUNT(*) as count, SUM(size_bytes) as total_size
        FROM files
        GROUP BY category
        ORDER BY total_size DESC
    """).fetchall()
    return [{"category": r[0] or "unknown", "count": r[1], "size": r[2]} for r in rows]


def _get_top_duplicates(db: FileDatabase, limit: int = 20) -> list[dict]:
    """Get top duplicate groups by wasted size."""
    duplicates = db.get_duplicates()
    result = []
    for d in duplicates[:limit]:
        size_each = d["total_size"] // d["count"]
        result.append({
            "count": d["count"],
            "size_each": size_each,
            "wasted": d["wasted_size"],
            "sample_path": d["paths"][0] if d["paths"] else "",
            "sample_name": Path(d["paths"][0]).name if d["paths"] else "",
        })
    return result


def _get_top_big_files(db: FileDatabase, limit: int = 20) -> list[dict]:
    """Get largest files."""
    rows = db.conn.execute("""
        SELECT path, name, size_bytes, extension, category
        FROM files
        ORDER BY size_bytes DESC
        LIMIT ?
    """, [limit]).fetchall()
    return [
        {"path": r[0], "name": r[1], "size": r[2], "ext": r[3] or "-", "category": r[4] or "-"}
        for r in rows
    ]


def generate_html_report(config: dict) -> str:
    """Generate the full HTML report string."""
    db_path = Path(config["database"]["path"]).expanduser()
    db = FileDatabase(str(db_path))

    stats = db.get_stats()
    ext_sizes = _get_size_by_extension(db)
    cat_sizes = _get_size_by_category(db)
    top_dups = _get_top_duplicates(db)
    top_big = _get_top_big_files(db)
    duplicates = db.get_duplicates()

    total_wasted = sum(d["wasted_size"] for d in duplicates)
    total_dup_sets = len(duplicates)
    total_dup_files = sum(d["count"] for d in duplicates)

    db.close()

    # Prepare chart data
    ext_labels = json.dumps([e["ext"] for e in ext_sizes])
    ext_values = json.dumps([e["size"] for e in ext_sizes])
    ext_counts = json.dumps([e["count"] for e in ext_sizes])

    cat_labels = json.dumps([c["category"] for c in cat_sizes])
    cat_values = json.dumps([c["size"] for c in cat_sizes])

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Doc Intelligence Report</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: #0f172a; color: #e2e8f0; padding: 2rem; }}
  .container {{ max-width: 1200px; margin: 0 auto; }}
  h1 {{ font-size: 2rem; margin-bottom: 0.5rem; color: #38bdf8; }}
  h2 {{ font-size: 1.3rem; margin-bottom: 1rem; color: #94a3b8; border-bottom: 1px solid #334155; padding-bottom: 0.5rem; }}
  .subtitle {{ color: #64748b; margin-bottom: 2rem; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1.5rem; margin-bottom: 2rem; }}
  .card {{ background: #1e293b; border-radius: 12px; padding: 1.5rem; border: 1px solid #334155; }}
  .card-value {{ font-size: 2rem; font-weight: 700; color: #38bdf8; }}
  .card-label {{ color: #94a3b8; font-size: 0.9rem; margin-top: 0.25rem; }}
  .card-accent {{ border-left: 4px solid #22c55e; }}
  .card-warn {{ border-left: 4px solid #f59e0b; }}
  .card-danger {{ border-left: 4px solid #ef4444; }}
  .chart-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 2rem; }}
  .chart-box {{ background: #1e293b; border-radius: 12px; padding: 1.5rem; border: 1px solid #334155; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 0.5rem; }}
  th {{ text-align: left; padding: 0.75rem; color: #94a3b8; font-weight: 600; border-bottom: 2px solid #334155; font-size: 0.85rem; }}
  td {{ padding: 0.75rem; border-bottom: 1px solid #1e293b; font-size: 0.9rem; }}
  tr:hover td {{ background: #1e293b; }}
  .size {{ color: #22c55e; font-weight: 600; }}
  .warn {{ color: #f59e0b; }}
  .path {{ color: #64748b; font-size: 0.8rem; word-break: break-all; }}
  .footer {{ text-align: center; color: #475569; margin-top: 3rem; font-size: 0.8rem; }}
  @media (max-width: 768px) {{ .chart-row {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<div class="container">
  <h1>Doc Intelligence Report</h1>
  <p class="subtitle">Generated {generated_at}</p>

  <div class="grid">
    <div class="card card-accent">
      <div class="card-value">{stats['total_files']:,}</div>
      <div class="card-label">Total Files Indexed</div>
    </div>
    <div class="card card-accent">
      <div class="card-value">{format_size(stats['total_size_bytes'])}</div>
      <div class="card-label">Total Storage Used</div>
    </div>
    <div class="card card-warn">
      <div class="card-value">{total_dup_sets:,}</div>
      <div class="card-label">Duplicate Sets ({total_dup_files:,} files)</div>
    </div>
    <div class="card card-danger">
      <div class="card-value">{format_size(total_wasted)}</div>
      <div class="card-label">Wasted by Duplicates</div>
    </div>
  </div>

  <div class="chart-row">
    <div class="chart-box">
      <h2>Storage by File Type</h2>
      <canvas id="extChart"></canvas>
    </div>
    <div class="chart-box">
      <h2>Storage by Category</h2>
      <canvas id="catChart"></canvas>
    </div>
  </div>

  <div class="card" style="margin-bottom: 2rem;">
    <h2>Largest Files</h2>
    <table>
      <thead><tr><th>#</th><th>Name</th><th>Size</th><th>Type</th><th>Category</th><th>Path</th></tr></thead>
      <tbody>
"""

    for i, f in enumerate(top_big, 1):
        path_display = f["path"]
        if len(path_display) > 70:
            path_display = "..." + path_display[-67:]
        html += f"""        <tr>
          <td>{i}</td>
          <td>{_html_escape(f['name'])}</td>
          <td class="size">{format_size(f['size'])}</td>
          <td>{_html_escape(f['ext'])}</td>
          <td>{_html_escape(f['category'])}</td>
          <td class="path">{_html_escape(path_display)}</td>
        </tr>
"""

    html += """      </tbody>
    </table>
  </div>

  <div class="card" style="margin-bottom: 2rem;">
    <h2>Top Duplicate Groups</h2>
"""

    if top_dups:
        html += """    <table>
      <thead><tr><th>#</th><th>File</th><th>Copies</th><th>Size Each</th><th class="warn">Wasted</th></tr></thead>
      <tbody>
"""
        for i, d in enumerate(top_dups, 1):
            html += f"""        <tr>
          <td>{i}</td>
          <td>{_html_escape(d['sample_name'])}</td>
          <td>{d['count']}</td>
          <td class="size">{format_size(d['size_each'])}</td>
          <td class="warn">{format_size(d['wasted'])}</td>
        </tr>
"""
        html += """      </tbody>
    </table>
"""
    else:
        html += '    <p style="color: #22c55e; padding: 1rem;">No duplicates found!</p>\n'

    html += f"""  </div>

  <div class="footer">
    Doc Intelligence v3.0 &middot; Report generated {generated_at}
  </div>
</div>

<script>
  const formatBytes = (bytes) => {{
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }};

  const colors = [
    '#38bdf8', '#22c55e', '#f59e0b', '#ef4444', '#a78bfa',
    '#f472b6', '#fb923c', '#34d399', '#60a5fa', '#c084fc',
    '#fbbf24', '#4ade80', '#f87171', '#818cf8', '#2dd4bf',
  ];

  new Chart(document.getElementById('extChart'), {{
    type: 'doughnut',
    data: {{
      labels: {ext_labels},
      datasets: [{{
        data: {ext_values},
        backgroundColor: colors,
        borderColor: '#0f172a',
        borderWidth: 2,
      }}]
    }},
    options: {{
      plugins: {{
        legend: {{ position: 'right', labels: {{ color: '#94a3b8', font: {{ size: 11 }} }} }},
        tooltip: {{
          callbacks: {{
            label: (ctx) => {{
              const counts = {ext_counts};
              return ctx.label + ': ' + formatBytes(ctx.raw) + ' (' + counts[ctx.dataIndex] + ' files)';
            }}
          }}
        }}
      }}
    }}
  }});

  new Chart(document.getElementById('catChart'), {{
    type: 'doughnut',
    data: {{
      labels: {cat_labels},
      datasets: [{{
        data: {cat_values},
        backgroundColor: colors,
        borderColor: '#0f172a',
        borderWidth: 2,
      }}]
    }},
    options: {{
      plugins: {{
        legend: {{ position: 'right', labels: {{ color: '#94a3b8', font: {{ size: 11 }} }} }},
        tooltip: {{
          callbacks: {{
            label: (ctx) => ctx.label + ': ' + formatBytes(ctx.raw)
          }}
        }}
      }}
    }}
  }});
</script>
</body>
</html>"""

    return html


def _html_escape(text: str) -> str:
    """Basic HTML escaping."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def run_report(
    config: Optional[dict] = None,
    config_path: Optional[str] = None,
    output_path: str = "doc_intelligence_report.html",
):
    """Generate and save the HTML report."""
    if config is None:
        config = load_config(config_path)

    db_path = Path(config["database"]["path"]).expanduser()
    if not db_path.exists():
        console.print("[red]Database not found. Run 'doc-intelligence scan' first.[/red]")
        return

    console.print("[cyan]Generating HTML report...[/cyan]")
    html = generate_html_report(config)

    output = Path(output_path)
    output.write_text(html, encoding="utf-8")

    console.print(f"[green]Report saved to {output.resolve()}[/green]")
    console.print(f"[dim]Open in your browser: file://{output.resolve()}[/dim]")


@app.callback(invoke_without_command=True)
def report(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config YAML file"),
    output: str = typer.Option("doc_intelligence_report.html", "--output", "-o", help="Output file path"),
):
    """Generate an HTML report of your file index."""
    run_report(config_path=config, output_path=output)


def main():
    app()


if __name__ == "__main__":
    main()
