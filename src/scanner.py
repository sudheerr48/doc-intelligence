"""
File Scanner Module - Fully Parallel & Incremental
Walks directories and computes file hashes using multiprocessing.
Supports incremental scanning (skip unchanged files).
"""

import os
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Iterator, Optional, List, Tuple, Dict, Set
from dataclasses import dataclass, asdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

import xxhash


# Number of workers for parallel processing
NUM_WORKERS = min(8, multiprocessing.cpu_count())


@dataclass
class FileInfo:
    """Information about a scanned file."""
    path: str
    name: str
    extension: str
    size_bytes: int
    created_at: datetime
    modified_at: datetime
    content_hash: Optional[str] = None
    category: Optional[str] = None
    content_text: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScanResult:
    """Result of scanning a folder."""
    new_files: List[FileInfo]
    unchanged_count: int
    removed_count: int
    total_size: int


def compute_hash(file_path: str, algorithm: str = "xxhash") -> Optional[str]:
    """
    Compute hash of file contents.
    
    Args:
        file_path: Path to the file
        algorithm: Hash algorithm ('sha256', 'md5', 'xxhash')
    
    Returns:
        Hex digest of file contents, or None if file can't be read
    """
    try:
        if algorithm == "xxhash":
            hasher = xxhash.xxh64()
        elif algorithm == "md5":
            hasher = hashlib.md5()
        else:
            hasher = hashlib.sha256()
        
        with open(file_path, "rb") as f:
            # Read in 1MB chunks for better I/O throughput
            for chunk in iter(lambda: f.read(1048576), b""):
                hasher.update(chunk)
        
        return hasher.hexdigest()
    except (IOError, PermissionError, OSError):
        return None


def should_skip(path: Path, exclude_patterns: list) -> bool:
    """Check if path should be skipped based on exclude patterns."""
    name = path.name
    
    for pattern in exclude_patterns:
        if pattern.startswith("*."):
            # Extension pattern
            if name.endswith(pattern[1:]):
                return True
        elif pattern in str(path):
            # Folder/path pattern
            return True
    
    return False


def _scan_and_hash_file(args: Tuple) -> Optional[Dict]:
    """
    Worker function: scan single file and compute hash.
    Also extracts text content for supported file types.
    Returns dict for easy serialization across processes.
    """
    file_path_str, category, min_size, hash_algo, exclude_patterns = args

    file_path = Path(file_path_str)

    # Skip excluded files
    if should_skip(file_path, exclude_patterns):
        return None

    # Skip symlinks
    if file_path.is_symlink():
        return None

    try:
        stat = file_path.stat()
    except (OSError, PermissionError):
        return None

    # Skip small files
    if stat.st_size < min_size:
        return None

    # Compute hash
    content_hash = compute_hash(file_path_str, hash_algo)

    # Extract text content for supported types
    from src.extractors import extract_text
    content_text = extract_text(file_path_str)

    return {
        "path": file_path_str,
        "name": file_path.name,
        "extension": file_path.suffix.lower(),
        "size_bytes": stat.st_size,
        "created_at": datetime.fromtimestamp(stat.st_ctime),
        "modified_at": datetime.fromtimestamp(stat.st_mtime),
        "content_hash": content_hash,
        "category": category,
        "content_text": content_text
    }


def _collect_files_with_stats(
    root_path: str,
    exclude_patterns: list,
    include_extensions: Optional[list] = None,
    min_size_bytes: int = 0
) -> List[Tuple[str, int, float]]:
    """
    Collect all file paths with their size and modification time.
    Returns: List of (path, size_bytes, mtime)
    """
    root = Path(root_path).expanduser().resolve()
    files = []
    
    if not root.exists():
        return files
    
    for dirpath, dirnames, filenames in os.walk(root):
        current_dir = Path(dirpath)
        
        # Filter out excluded directories in-place
        dirnames[:] = [
            d for d in dirnames 
            if not should_skip(current_dir / d, exclude_patterns)
        ]
        
        for filename in filenames:
            file_path = current_dir / filename
            
            # Skip excluded
            if should_skip(file_path, exclude_patterns):
                continue
            
            # Skip symlinks
            if file_path.is_symlink():
                continue
            
            # Quick filter by extension if specified
            if include_extensions:
                ext = file_path.suffix.lower()
                if ext not in include_extensions:
                    continue
            
            try:
                stat = file_path.stat()
                if stat.st_size >= min_size_bytes:
                    files.append((str(file_path), stat.st_size, stat.st_mtime))
            except (OSError, PermissionError):
                continue
    
    return files


def scan_folder_incremental(
    root_path: str,
    category: str,
    cached_files: Dict[str, Dict],  # path -> {modified_at, size_bytes, content_hash}
    include_extensions: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
    min_size_bytes: int = 0,
    hash_algorithm: str = "xxhash",
    num_workers: int = NUM_WORKERS
) -> ScanResult:
    """
    Scan a folder incrementally - only process new/modified files.
    
    Args:
        root_path: Directory to scan
        category: Category label for files
        cached_files: Dict of already-scanned files from DB
        include_extensions: Only include these extensions
        exclude_patterns: Patterns to exclude
        min_size_bytes: Skip files smaller than this
        hash_algorithm: Hash algorithm to use
        num_workers: Number of parallel workers
    
    Returns:
        ScanResult with new files, counts, etc.
    """
    exclude_patterns = exclude_patterns or []
    
    # Phase 1: Collect all files with stats
    all_files = _collect_files_with_stats(
        root_path, exclude_patterns, include_extensions, min_size_bytes
    )
    
    # Determine which files need scanning
    files_to_scan = []
    unchanged_files = []
    current_paths = set()
    total_size = 0
    
    for file_path, size_bytes, mtime in all_files:
        current_paths.add(file_path)
        total_size += size_bytes
        
        # Check if file is in cache and unchanged
        if file_path in cached_files:
            cached = cached_files[file_path]
            cached_mtime = cached["modified_at"]
            
            # Compare modification times (allow small tolerance for float comparison)
            if cached_mtime:
                # Convert datetime to timestamp if needed
                if isinstance(cached_mtime, datetime):
                    cached_ts = cached_mtime.timestamp()
                else:
                    cached_ts = float(cached_mtime)
                
                # File unchanged if mtime matches (within 1 second tolerance)
                if abs(mtime - cached_ts) < 1.0 and cached["size_bytes"] == size_bytes:
                    unchanged_files.append(file_path)
                    continue
        
        # File is new or modified - needs scanning
        files_to_scan.append(file_path)
    
    # Phase 2: Process only new/modified files in parallel
    new_files = []
    
    if files_to_scan:
        work_args = [
            (fp, category, min_size_bytes, hash_algorithm, exclude_patterns)
            for fp in files_to_scan
        ]
        
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(_scan_and_hash_file, args) for args in work_args]
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        new_files.append(FileInfo(**result))
                except Exception:
                    pass
    
    # Calculate removed files (in cache but not on disk)
    cached_paths = set(cached_files.keys())
    removed_count = len(cached_paths - current_paths)
    
    return ScanResult(
        new_files=new_files,
        unchanged_count=len(unchanged_files),
        removed_count=removed_count,
        total_size=total_size
    )


# Legacy function for compatibility
def scan_folder_parallel(
    root_path: str,
    category: str = "unknown",
    include_extensions: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
    min_size_bytes: int = 0,
    hash_algorithm: str = "xxhash",
    num_workers: int = NUM_WORKERS
) -> List[FileInfo]:
    """Scan a folder (non-incremental, for backwards compatibility)."""
    result = scan_folder_incremental(
        root_path=root_path,
        category=category,
        cached_files={},  # Empty cache = scan everything
        include_extensions=include_extensions,
        exclude_patterns=exclude_patterns,
        min_size_bytes=min_size_bytes,
        hash_algorithm=hash_algorithm,
        num_workers=num_workers
    )
    return result.new_files
