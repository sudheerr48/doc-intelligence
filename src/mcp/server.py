"""
MCP Server — exposes doc-intelligence as Model Context Protocol tools.
"""

import json
from pathlib import Path
from typing import Optional

from src.core.config import load_config, format_size
from src.core.database import FileDatabase


def _get_db(config_path: Optional[str] = None) -> tuple[dict, FileDatabase]:
    config = load_config(config_path)
    db_path = Path(config["database"]["path"]).expanduser()
    if not db_path.exists():
        raise FileNotFoundError(
            f"Database not found at {db_path}. "
            "Run 'doc-intelligence scan' first."
        )
    return config, FileDatabase(str(db_path))


def create_mcp_server(config_path: Optional[str] = None):
    """Create and configure the MCP server with all doc-intelligence tools."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        raise ImportError(
            "MCP server requires the 'mcp' package.\n"
            "Install with: pip install 'doc-intelligence[mcp]'"
        )

    mcp = FastMCP(
        "doc-intelligence",
        description=(
            "AI-powered file intelligence — search, deduplicate, "
            "tag, and analyze your files."
        ),
    )

    _config_path = config_path

    @mcp.tool()
    def search_files(query: str, limit: int = 50) -> str:
        """Search files by name, path, or content text."""
        _, db = _get_db(_config_path)
        try:
            results = db.search(query, limit=limit)
            if not results:
                return "No files found matching your query."
            lines = [f"Found {len(results)} files:\n"]
            for r in results:
                match = " (content match)" if r.get("content_match") else ""
                lines.append(
                    f"  {r['name']} ({format_size(r['size_bytes'])}) "
                    f"[{r['category']}]{match}\n    {r['path']}"
                )
            return "\n".join(lines)
        finally:
            db.close()

    @mcp.tool()
    def get_statistics() -> str:
        """Get database statistics."""
        _, db = _get_db(_config_path)
        try:
            stats = db.get_stats()
            parts = [
                f"Total files: {stats['total_files']:,}",
                f"Total size: {format_size(stats['total_size_bytes'])}",
                f"Duplicate sets: {stats['duplicate_sets']:,}",
            ]
            if stats["by_category"]:
                parts.append("\nBy category:")
                for cat, count in sorted(
                    stats["by_category"].items(),
                    key=lambda x: x[1], reverse=True,
                ):
                    parts.append(f"  {cat}: {count:,} files")
            if stats["by_extension"]:
                parts.append("\nTop extensions:")
                for ext, count in list(stats["by_extension"].items())[:10]:
                    parts.append(f"  {ext or '(none)'}: {count:,} files")
            return "\n".join(parts)
        finally:
            db.close()

    @mcp.tool()
    def find_duplicates(limit: int = 20) -> str:
        """Find duplicate files (same content hash)."""
        _, db = _get_db(_config_path)
        try:
            duplicates = db.get_duplicates()
            if not duplicates:
                return "No duplicate files found!"
            total_wasted = sum(d["wasted_size"] for d in duplicates)
            lines = [
                f"Found {len(duplicates)} duplicate sets "
                f"(reclaimable: {format_size(total_wasted)})\n"
            ]
            for i, dup in enumerate(duplicates[:limit], 1):
                size_each = dup["total_size"] // dup["count"]
                lines.append(
                    f"{i}. {dup['count']} copies, "
                    f"{format_size(size_each)} each "
                    f"(wasting {format_size(dup['wasted_size'])})"
                )
                for p in dup["paths"][:3]:
                    lines.append(f"   {p}")
                if len(dup["paths"]) > 3:
                    lines.append(
                        f"   ... and {len(dup['paths']) - 3} more"
                    )
                lines.append("")
            return "\n".join(lines)
        finally:
            db.close()

    @mcp.tool()
    def get_health_report() -> str:
        """Generate a file system health report."""
        _, db = _get_db(_config_path)
        try:
            from src.analysis.health import (
                compute_health_score,
                generate_health_text,
            )
            metrics = db.get_health_metrics()
            health = compute_health_score(metrics)
            return generate_health_text(metrics, health)
        finally:
            db.close()

    @mcp.tool()
    def browse_tags(tag_name: Optional[str] = None) -> str:
        """Browse file tags or look up files for a specific tag."""
        _, db = _get_db(_config_path)
        try:
            if tag_name:
                files = db.get_files_by_tag(tag_name, limit=100)
                if not files:
                    return f"No files found with tag '{tag_name}'."
                lines = [
                    f"Files tagged '{tag_name}' ({len(files)} results):\n"
                ]
                for f in files:
                    tags_str = ", ".join(f.get("tags", [])[:5])
                    lines.append(
                        f"  {f['name']} ({format_size(f['size_bytes'])}) "
                        f"[{f['category']}]\n"
                        f"    Tags: {tags_str}\n    {f['path']}"
                    )
                return "\n".join(lines)
            else:
                all_tags = db.get_all_tags()
                if not all_tags:
                    return (
                        "No tags found. "
                        "Run 'doc-intelligence tag' to classify files."
                    )
                lines = [f"{len(all_tags)} unique tags:\n"]
                for tag, count in all_tags.items():
                    lines.append(f"  {tag}: {count} files")
                return "\n".join(lines)
        finally:
            db.close()

    @mcp.tool()
    def run_sql_query(sql: str) -> str:
        """Execute a read-only SQL query against the file index."""
        _, db = _get_db(_config_path)
        try:
            results = db.run_query(sql)
            if not results:
                return "Query returned no results."
            columns = list(results[0].keys())
            lines = [" | ".join(columns), "-" * (len(" | ".join(columns)))]
            for row in results[:100]:
                vals = []
                for col in columns:
                    val = row[col]
                    if val is None:
                        vals.append("-")
                    elif isinstance(val, (int, float)) and "size" in col.lower():
                        vals.append(format_size(int(val)))
                    else:
                        s = str(val)
                        if len(s) > 60:
                            s = s[:57] + "..."
                        vals.append(s)
                lines.append(" | ".join(vals))
            if len(results) > 100:
                lines.append(
                    f"\n... {len(results) - 100} more rows truncated"
                )
            return "\n".join(lines)
        finally:
            db.close()

    @mcp.tool()
    def find_large_files(
        top_n: int = 20, extension: Optional[str] = None,
    ) -> str:
        """Find the largest files in the index."""
        _, db = _get_db(_config_path)
        try:
            sql = (
                "SELECT path, name, extension, size_bytes, category FROM files"
            )
            params = []
            if extension:
                ext = (
                    extension if extension.startswith(".") else f".{extension}"
                )
                sql += " WHERE extension = ?"
                params.append(ext)
            sql += f" ORDER BY size_bytes DESC LIMIT {int(top_n)}"
            results = db.run_query(sql, params if params else None)
            if not results:
                return "No files found."
            lines = [f"Top {len(results)} largest files:\n"]
            for i, r in enumerate(results, 1):
                lines.append(
                    f"  {i}. {r['name']} — "
                    f"{format_size(r['size_bytes'])} [{r['category']}]\n"
                    f"     {r['path']}"
                )
            return "\n".join(lines)
        finally:
            db.close()

    @mcp.tool()
    def semantic_search(
        query: str, limit: int = 20, threshold: float = 0.3,
    ) -> str:
        """Search files by meaning using embeddings."""
        _, db = _get_db(_config_path)
        try:
            embed_stats = db.get_embedding_stats()
            if embed_stats["embedded_files"] == 0:
                return (
                    "No embeddings found. "
                    "Run 'doc-intelligence embed' first."
                )
            from src.ai.embeddings import generate_embeddings
            from src.ai.providers import is_embedding_available
            if not is_embedding_available():
                return (
                    "Embedding API not available. "
                    "Set OPENAI_API_KEY or VOYAGE_API_KEY."
                )
            query_vec = generate_embeddings([query])[0]
            results = db.semantic_search(query_vec, limit=limit)
            results = [r for r in results if r["similarity"] >= threshold]
            if not results:
                return "No similar files found above the threshold."
            lines = [f"Found {len(results)} similar files:\n"]
            for r in results:
                tags_str = ""
                if r.get("tags"):
                    try:
                        tag_list = (
                            json.loads(r["tags"])
                            if isinstance(r["tags"], str) else []
                        )
                        tags_str = f" tags=[{', '.join(tag_list[:3])}]"
                    except (TypeError, json.JSONDecodeError):
                        pass
                lines.append(
                    f"  {r['similarity']:.2f}  {r['name']} "
                    f"({format_size(r['size_bytes'])}){tags_str}\n"
                    f"         {r['path']}"
                )
            return "\n".join(lines)
        finally:
            db.close()

    @mcp.resource("schema://files")
    def get_schema() -> str:
        """The DuckDB schema for the files table."""
        return (
            "CREATE TABLE files (\n"
            "    path VARCHAR PRIMARY KEY,\n"
            "    name VARCHAR,\n"
            "    extension VARCHAR,\n"
            "    size_bytes BIGINT,\n"
            "    created_at TIMESTAMP,\n"
            "    modified_at TIMESTAMP,\n"
            "    content_hash VARCHAR,\n"
            "    category VARCHAR,\n"
            "    scanned_at TIMESTAMP,\n"
            "    content_text VARCHAR,\n"
            "    tags VARCHAR  -- JSON array\n"
            ");\n\n"
            "CREATE TABLE embeddings (\n"
            "    path VARCHAR PRIMARY KEY,\n"
            "    embedding BLOB,\n"
            "    model VARCHAR,\n"
            "    embedded_at TIMESTAMP\n"
            ");"
        )

    return mcp


def run_mcp_server(
    config_path: Optional[str] = None,
    transport: str = "stdio",
    port: int = 8765,
):
    """Start the MCP server."""
    server = create_mcp_server(config_path)
    if transport == "stdio":
        server.run(transport="stdio")
    elif transport == "http":
        server.run(
            transport="streamable-http", host="127.0.0.1", port=port,
        )
    else:
        raise ValueError(
            f"Unknown transport: {transport}. Use 'stdio' or 'http'."
        )
