"""
Storage Module
DuckDB operations for file metadata storage.
"""

import json
from pathlib import Path
from typing import Optional
from datetime import datetime

import duckdb

from .scanner import FileInfo


class FileDatabase:
    """DuckDB-backed file metadata storage."""
    
    def __init__(self, db_path: str):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to DuckDB database file
        """
        self.db_path = Path(db_path).expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = duckdb.connect(str(self.db_path))
        self._create_tables()
    
    def _create_tables(self):
        """Create database tables if they don't exist."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS files (
                path VARCHAR PRIMARY KEY,
                name VARCHAR,
                extension VARCHAR,
                size_bytes BIGINT,
                created_at TIMESTAMP,
                modified_at TIMESTAMP,
                content_hash VARCHAR,
                category VARCHAR,
                scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                content_text VARCHAR
            )
        """)

        # Migrate existing databases: add missing columns
        columns = {
            row[0] for row in
            self.conn.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'files'").fetchall()
        }
        if "content_text" not in columns:
            self.conn.execute("ALTER TABLE files ADD COLUMN content_text VARCHAR")
        if "tags" not in columns:
            self.conn.execute("ALTER TABLE files ADD COLUMN tags VARCHAR")

        # Index for fast duplicate lookups
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_content_hash
            ON files(content_hash)
        """)

        # Index for extension-based queries
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_extension
            ON files(extension)
        """)
    
    def insert_file(self, file_info: FileInfo) -> bool:
        """
        Insert or update a file record.

        Args:
            file_info: FileInfo object to insert

        Returns:
            True if inserted, False if error
        """
        try:
            self.conn.execute("DELETE FROM files WHERE path = ?", [file_info.path])
            self.conn.execute("""
                INSERT INTO files
                (path, name, extension, size_bytes, created_at, modified_at,
                 content_hash, category, content_text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                file_info.path,
                file_info.name,
                file_info.extension,
                file_info.size_bytes,
                file_info.created_at,
                file_info.modified_at,
                file_info.content_hash,
                file_info.category,
                file_info.content_text
            ])
            return True
        except Exception as e:
            print(f"Error inserting {file_info.path}: {e}")
            return False

    def insert_batch(self, files: list[FileInfo]) -> int:
        """
        Insert multiple files efficiently using bulk operations.

        Uses batched DELETE + single-statement multi-row INSERT for
        significant speedup over row-by-row operations.

        Args:
            files: List of FileInfo objects

        Returns:
            Number of files inserted
        """
        if not files:
            return 0

        try:
            batch_size = 500
            paths = [fi.path for fi in files]

            # Bulk delete existing rows for these paths
            for i in range(0, len(paths), batch_size):
                batch = paths[i:i + batch_size]
                placeholders = ", ".join(["?" for _ in batch])
                self.conn.execute(
                    f"DELETE FROM files WHERE path IN ({placeholders})", batch
                )

            # Bulk insert using single multi-row VALUES statement
            for i in range(0, len(files), batch_size):
                chunk = files[i:i + batch_size]
                row_placeholder = "(?, ?, ?, ?, ?, ?, ?, ?, ?)"
                values_sql = ", ".join([row_placeholder] * len(chunk))
                flat_params = []
                for fi in chunk:
                    flat_params.extend([
                        fi.path, fi.name, fi.extension, fi.size_bytes,
                        fi.created_at, fi.modified_at, fi.content_hash,
                        fi.category, fi.content_text
                    ])
                self.conn.execute(
                    f"INSERT INTO files "
                    f"(path, name, extension, size_bytes, created_at, "
                    f"modified_at, content_hash, category, content_text) "
                    f"VALUES {values_sql}",
                    flat_params
                )
            return len(files)
        except Exception as e:
            print(f"Error in batch insert: {e}")
            return 0
    
    def get_duplicates(self) -> list[dict]:
        """
        Find all duplicate files (same content hash).
        
        Returns:
            List of duplicate groups, each containing file paths
        """
        result = self.conn.execute("""
            SELECT content_hash, 
                   COUNT(*) as count,
                   SUM(size_bytes) as total_size,
                   LIST(path) as paths
            FROM files
            WHERE content_hash IS NOT NULL
            GROUP BY content_hash
            HAVING COUNT(*) > 1
            ORDER BY total_size DESC
        """).fetchall()
        
        return [
            {
                "hash": row[0],
                "count": row[1],
                "total_size": row[2],
                "wasted_size": row[2] - (row[2] // row[1]),  # Size that could be freed
                "paths": row[3]
            }
            for row in result
        ]
    
    def get_stats(self) -> dict:
        """Get database statistics."""
        stats = {}
        
        # Total files
        stats["total_files"] = self.conn.execute(
            "SELECT COUNT(*) FROM files"
        ).fetchone()[0]
        
        # Total size
        stats["total_size_bytes"] = self.conn.execute(
            "SELECT SUM(size_bytes) FROM files"
        ).fetchone()[0] or 0
        
        # By category
        stats["by_category"] = {
            row[0]: row[1] 
            for row in self.conn.execute(
                "SELECT category, COUNT(*) FROM files GROUP BY category"
            ).fetchall()
        }
        
        # By extension
        stats["by_extension"] = {
            row[0]: row[1] 
            for row in self.conn.execute(
                "SELECT extension, COUNT(*) FROM files GROUP BY extension ORDER BY COUNT(*) DESC LIMIT 20"
            ).fetchall()
        }
        
        # Duplicate count
        dup_result = self.conn.execute("""
            SELECT COUNT(*) FROM (
                SELECT content_hash FROM files 
                WHERE content_hash IS NOT NULL
                GROUP BY content_hash HAVING COUNT(*) > 1
            )
        """).fetchone()
        stats["duplicate_sets"] = dup_result[0] if dup_result else 0
        
        return stats
    
    def search(self, query: str, limit: int = 50) -> list[dict]:
        """
        Search files by name, path, or content text.

        Args:
            query: Search query (case-insensitive)
            limit: Maximum results

        Returns:
            List of matching files
        """
        like_param = f"%{query}%"
        result = self.conn.execute("""
            SELECT path, name, extension, size_bytes, category,
                   CASE
                       WHEN LOWER(content_text) LIKE LOWER(?) THEN 1
                       ELSE 0
                   END AS content_match
            FROM files
            WHERE LOWER(name) LIKE LOWER(?)
               OR LOWER(path) LIKE LOWER(?)
               OR LOWER(content_text) LIKE LOWER(?)
            ORDER BY content_match DESC, modified_at DESC
            LIMIT ?
        """, [like_param, like_param, like_param, like_param, limit]).fetchall()

        return [
            {
                "path": row[0],
                "name": row[1],
                "extension": row[2],
                "size_bytes": row[3],
                "category": row[4],
                "content_match": bool(row[5])
            }
            for row in result
        ]
    
    def clear(self):
        """Clear all data from the database."""
        self.conn.execute("DELETE FROM files")
    
    def get_cached_file_info(self, paths: list[str]) -> dict:
        """
        Get cached modification times for files.
        Used for incremental scanning.
        
        Args:
            paths: List of file paths to check
        
        Returns:
            Dict mapping path -> (modified_at, size_bytes, content_hash)
        """
        if not paths:
            return {}
        
        # Query in batches to avoid SQL limits
        result = {}
        batch_size = 500
        
        for i in range(0, len(paths), batch_size):
            batch = paths[i:i + batch_size]
            placeholders = ", ".join(["?" for _ in batch])
            rows = self.conn.execute(f"""
                SELECT path, modified_at, size_bytes, content_hash
                FROM files
                WHERE path IN ({placeholders})
            """, batch).fetchall()
            
            for row in rows:
                result[row[0]] = {
                    "modified_at": row[1],
                    "size_bytes": row[2],
                    "content_hash": row[3]
                }
        
        return result
    
    def get_paths_for_category(self, category: str) -> set:
        """Get all file paths for a category."""
        rows = self.conn.execute(
            "SELECT path FROM files WHERE category = ?", [category]
        ).fetchall()
        return {row[0] for row in rows}
    
    def update_tags(self, path: str, tags: list[str]) -> bool:
        """
        Update tags for a file.

        Args:
            path: File path (primary key)
            tags: List of tag strings

        Returns:
            True if updated, False if error
        """
        try:
            tags_json = json.dumps(tags)
            self.conn.execute(
                "UPDATE files SET tags = ? WHERE path = ?",
                [tags_json, path]
            )
            return True
        except Exception:
            return False

    def batch_update_tags(self, tag_map: dict[str, list[str]]) -> int:
        """
        Update tags for multiple files.

        Args:
            tag_map: Dict mapping path -> list of tags

        Returns:
            Number of files updated
        """
        count = 0
        for path, tags in tag_map.items():
            if self.update_tags(path, tags):
                count += 1
        return count

    def get_all_tags(self) -> dict[str, int]:
        """
        Get all unique tags with their file counts.

        Returns:
            Dict mapping tag -> count
        """
        rows = self.conn.execute("""
            SELECT tags FROM files WHERE tags IS NOT NULL AND tags != '[]'
        """).fetchall()

        tag_counts: dict[str, int] = {}
        for (tags_json,) in rows:
            try:
                tags = json.loads(tags_json)
                for tag in tags:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
            except (json.JSONDecodeError, TypeError):
                continue
        return dict(sorted(tag_counts.items(), key=lambda x: x[1], reverse=True))

    def get_files_by_tag(self, tag: str, limit: int = 100) -> list[dict]:
        """
        Get all files matching a tag.

        Args:
            tag: Tag to search for
            limit: Maximum results

        Returns:
            List of matching file dicts
        """
        rows = self.conn.execute("""
            SELECT path, name, extension, size_bytes, category, tags
            FROM files
            WHERE tags IS NOT NULL AND tags LIKE ?
            ORDER BY size_bytes DESC
            LIMIT ?
        """, [f'%"{tag}"%', limit]).fetchall()

        return [
            {
                "path": r[0], "name": r[1], "extension": r[2],
                "size_bytes": r[3], "category": r[4],
                "tags": json.loads(r[5]) if r[5] else [],
            }
            for r in rows
        ]

    def get_untagged_files(self, limit: int = 500) -> list[dict]:
        """Get files that haven't been tagged yet."""
        rows = self.conn.execute("""
            SELECT path, name, extension, size_bytes, category, content_text
            FROM files
            WHERE tags IS NULL OR tags = '[]'
            ORDER BY size_bytes DESC
            LIMIT ?
        """, [limit]).fetchall()

        return [
            {
                "path": r[0], "name": r[1], "extension": r[2],
                "size_bytes": r[3], "category": r[4],
                "content_text": r[5],
            }
            for r in rows
        ]

    def run_query(self, sql: str, params: list = None) -> list[dict]:
        """
        Execute a read-only SQL query and return results as dicts.
        Used by natural language query engine.

        Args:
            sql: SQL query (SELECT only)
            params: Optional query parameters

        Returns:
            List of result rows as dicts
        """
        sql_stripped = sql.strip().upper()
        if not sql_stripped.startswith("SELECT"):
            raise ValueError("Only SELECT queries are allowed")

        # Block dangerous operations
        for keyword in ("DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE", "TRUNCATE"):
            if keyword in sql_stripped:
                raise ValueError(f"Query contains forbidden keyword: {keyword}")

        try:
            if params:
                result = self.conn.execute(sql, params)
            else:
                result = self.conn.execute(sql)

            columns = [desc[0] for desc in result.description]
            rows = result.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            raise RuntimeError(f"Query execution failed: {e}")

    def get_health_metrics(self) -> dict:
        """
        Compute file system health metrics.

        Returns:
            Dict with health metrics for reporting
        """
        stats = self.get_stats()
        duplicates = self.get_duplicates()

        total_wasted = sum(d["wasted_size"] for d in duplicates)
        total_dup_files = sum(d["count"] for d in duplicates)

        # Stale files (not modified in 365+ days)
        stale_result = self.conn.execute("""
            SELECT COUNT(*), COALESCE(SUM(size_bytes), 0)
            FROM files
            WHERE modified_at < CURRENT_TIMESTAMP - INTERVAL '365 days'
        """).fetchone()
        stale_count = stale_result[0]
        stale_size = stale_result[1]

        # Large files (> 100MB)
        large_result = self.conn.execute("""
            SELECT COUNT(*), COALESCE(SUM(size_bytes), 0)
            FROM files
            WHERE size_bytes > 104857600
        """).fetchone()
        large_count = large_result[0]
        large_size = large_result[1]

        # Top 10 largest files
        top_large = self.conn.execute("""
            SELECT path, name, size_bytes, extension, category
            FROM files ORDER BY size_bytes DESC LIMIT 10
        """).fetchall()

        # New files (added in last 7 days based on scanned_at)
        new_result = self.conn.execute("""
            SELECT COUNT(*), COALESCE(SUM(size_bytes), 0)
            FROM files
            WHERE scanned_at > CURRENT_TIMESTAMP - INTERVAL '7 days'
        """).fetchone()

        # Extension diversity
        ext_count = self.conn.execute(
            "SELECT COUNT(DISTINCT extension) FROM files"
        ).fetchone()[0]

        # Category breakdown with sizes
        category_breakdown = self.conn.execute("""
            SELECT category, COUNT(*) as files, SUM(size_bytes) as total_size
            FROM files GROUP BY category ORDER BY total_size DESC
        """).fetchall()

        # Top 10 duplicate groups
        top_dups = []
        for d in duplicates[:10]:
            size_each = d["total_size"] // d["count"]
            top_dups.append({
                "count": d["count"],
                "size_each": size_each,
                "wasted": d["wasted_size"],
                "sample": Path(d["paths"][0]).name if d["paths"] else "",
            })

        # Tagged vs untagged
        tagged_result = self.conn.execute("""
            SELECT COUNT(*) FROM files WHERE tags IS NOT NULL AND tags != '[]'
        """).fetchone()
        tagged_count = tagged_result[0]

        return {
            "total_files": stats["total_files"],
            "total_size": stats["total_size_bytes"],
            "duplicate_sets": len(duplicates),
            "duplicate_files": total_dup_files,
            "wasted_by_duplicates": total_wasted,
            "stale_files": stale_count,
            "stale_size": stale_size,
            "large_files": large_count,
            "large_size": large_size,
            "top_large_files": [
                {"path": r[0], "name": r[1], "size": r[2], "ext": r[3], "category": r[4]}
                for r in top_large
            ],
            "new_files_7d": new_result[0],
            "new_size_7d": new_result[1],
            "extension_types": ext_count,
            "category_breakdown": [
                {"category": r[0] or "unknown", "files": r[1], "size": r[2]}
                for r in category_breakdown
            ],
            "top_duplicates": top_dups,
            "tagged_files": tagged_count,
            "untagged_files": stats["total_files"] - tagged_count,
            "by_extension": stats["by_extension"],
        }

    def remove_missing_files(self, valid_paths: set, category: str) -> int:
        """
        Remove files from DB that no longer exist on disk.
        
        Args:
            valid_paths: Set of paths that still exist
            category: Category to clean
        
        Returns:
            Number of files removed
        """
        current_paths = self.get_paths_for_category(category)
        missing = current_paths - valid_paths
        
        if missing:
            placeholders = ", ".join(["?" for _ in missing])
            self.conn.execute(f"DELETE FROM files WHERE path IN ({placeholders})", list(missing))
        
        return len(missing)
    
    def close(self):
        """Close database connection."""
        self.conn.close()

