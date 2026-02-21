"""
Natural language to SQL query generation.
"""

from typing import Optional

from .providers import chat, chat_with_tool, default_model


NL_QUERY_SYSTEM = """\
You are a SQL query generator for a DuckDB database. The database has a single \
table called `files` with this schema:

CREATE TABLE files (
    path VARCHAR PRIMARY KEY,
    name VARCHAR,
    extension VARCHAR,
    size_bytes BIGINT,
    created_at TIMESTAMP,
    modified_at TIMESTAMP,
    content_hash VARCHAR,
    category VARCHAR,
    scanned_at TIMESTAMP,
    content_text VARCHAR,
    tags VARCHAR  -- JSON array of strings, e.g. '["finance", "invoice-pdf"]'
);

Rules:
- Generate a valid DuckDB SELECT query.
- Use ILIKE for case-insensitive text matching.
- For tag queries, use: tags LIKE '%"tag-name"%'
- For size queries: 1 KB = 1024, 1 MB = 1048576, 1 GB = 1073741824
- Always add LIMIT 100 unless the user specifies a different limit.
- For aggregation queries (count, sum, avg), still limit grouping results.
- Common patterns:
  - "PDFs over 10MB" -> extension = '.pdf' AND size_bytes > 10485760
  - "duplicate files" -> GROUP BY content_hash HAVING COUNT(*) > 1
  - "largest files" -> ORDER BY size_bytes DESC
  - "recently modified" -> ORDER BY modified_at DESC
  - "files tagged as X" -> tags LIKE '%"X"%'\
"""

_SQL_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "sql": {
            "type": "string",
            "description": "A valid DuckDB SELECT query",
        }
    },
    "required": ["sql"],
}


def nl_to_sql(query: str, model: Optional[str] = None) -> str:
    """Convert a natural language query to a DuckDB SQL SELECT statement."""
    try:
        result = chat_with_tool(
            system=NL_QUERY_SYSTEM,
            user_msg=query,
            model=default_model(model),
            max_tokens=500,
            tool_name="generate_sql",
            tool_description="Generate a DuckDB SELECT query from natural language",
            tool_schema=_SQL_TOOL_SCHEMA,
        )
        return result["sql"]
    except Exception:
        sql = chat(
            NL_QUERY_SYSTEM + "\nReturn ONLY the SQL query.",
            query, default_model(model), max_tokens=500,
        )
        if sql.startswith("```"):
            lines = sql.split("\n")
            lines = [ln for ln in lines if not ln.startswith("```")]
            sql = "\n".join(lines).strip()
        return sql
