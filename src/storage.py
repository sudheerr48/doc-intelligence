"""
Storage Module
DuckDB operations for file metadata storage.
"""

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
                scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
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
            # Simple insert - delete first if exists
            self.conn.execute("DELETE FROM files WHERE path = ?", [file_info.path])
            self.conn.execute("""
                INSERT INTO files 
                (path, name, extension, size_bytes, created_at, modified_at, content_hash, category)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                file_info.path,
                file_info.name,
                file_info.extension,
                file_info.size_bytes,
                file_info.created_at,
                file_info.modified_at,
                file_info.content_hash,
                file_info.category
            ])
            return True
        except Exception as e:
            print(f"Error inserting {file_info.path}: {e}")
            return False
    
    def insert_batch(self, files: list[FileInfo]) -> int:
        """
        Insert multiple files efficiently.
        
        Args:
            files: List of FileInfo objects
        
        Returns:
            Number of files inserted
        """
        count = 0
        for file_info in files:
            if self.insert_file(file_info):
                count += 1
        return count
    
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
        Search files by name or path.
        
        Args:
            query: Search query (case-insensitive)
            limit: Maximum results
        
        Returns:
            List of matching files
        """
        result = self.conn.execute("""
            SELECT path, name, extension, size_bytes, category
            FROM files
            WHERE LOWER(name) LIKE LOWER(?) OR LOWER(path) LIKE LOWER(?)
            ORDER BY modified_at DESC
            LIMIT ?
        """, [f"%{query}%", f"%{query}%", limit]).fetchall()
        
        return [
            {
                "path": row[0],
                "name": row[1],
                "extension": row[2],
                "size_bytes": row[3],
                "category": row[4]
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

