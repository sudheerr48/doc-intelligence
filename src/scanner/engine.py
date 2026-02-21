"""
File scanning engine — directory walking, hashing, and incremental scanning.
"""

import os
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Tuple, Dict
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

import xxhash

from src.core.models import FileInfo, ScanResult

NUM_WORKERS = min(8, multiprocessing.cpu_count())


def compute_hash(file_path: str, algorithm: str = "xxhash") -> Optional[str]:
    """Compute hash of file contents."""
    try:
        if algorithm == "xxhash":
            hasher = xxhash.xxh64()
        elif algorithm == "md5":
            hasher = hashlib.md5()
        else:
            hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
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
            if name.endswith(pattern[1:]):
                return True
        elif pattern in str(path):
            return True
    return False


def _scan_and_hash_file(args: Tuple) -> Optional[Dict]:
    """Worker function: scan single file and compute hash + extract text."""
    file_path_str, category, min_size, hash_algo, exclude_patterns = args
    file_path = Path(file_path_str)

    if should_skip(file_path, exclude_patterns):
        return None
    if file_path.is_symlink():
        return None
    try:
        stat = file_path.stat()
    except (OSError, PermissionError):
        return None
    if stat.st_size < min_size:
        return None

    content_hash = compute_hash(file_path_str, hash_algo)

    from src.scanner.extractors import extract_text
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
        "content_text": content_text,
    }


def _collect_files_with_stats(
    root_path: str,
    exclude_patterns: list,
    include_extensions: Optional[list] = None,
    min_size_bytes: int = 0,
) -> List[Tuple[str, int, float]]:
    """Collect all file paths with their size and modification time."""
    root = Path(root_path).expanduser().resolve()
    files = []
    if not root.exists():
        return files

    for dirpath, dirnames, filenames in os.walk(root):
        current_dir = Path(dirpath)
        dirnames[:] = [
            d for d in dirnames
            if not should_skip(current_dir / d, exclude_patterns)
        ]
        for filename in filenames:
            file_path = current_dir / filename
            if should_skip(file_path, exclude_patterns):
                continue
            if file_path.is_symlink():
                continue
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
    cached_files: Dict[str, Dict],
    include_extensions: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
    min_size_bytes: int = 0,
    hash_algorithm: str = "xxhash",
    num_workers: int = NUM_WORKERS,
) -> ScanResult:
    """Scan a folder incrementally — only process new/modified files."""
    exclude_patterns = exclude_patterns or []

    all_files = _collect_files_with_stats(
        root_path, exclude_patterns, include_extensions, min_size_bytes,
    )

    files_to_scan = []
    unchanged_files = []
    current_paths = set()
    total_size = 0

    for file_path, size_bytes, mtime in all_files:
        current_paths.add(file_path)
        total_size += size_bytes

        if file_path in cached_files:
            cached = cached_files[file_path]
            cached_mtime = cached["modified_at"]
            if cached_mtime:
                if isinstance(cached_mtime, datetime):
                    cached_ts = cached_mtime.timestamp()
                else:
                    cached_ts = float(cached_mtime)
                if (abs(mtime - cached_ts) < 1.0
                        and cached["size_bytes"] == size_bytes):
                    unchanged_files.append(file_path)
                    continue

        files_to_scan.append(file_path)

    new_files = []
    if files_to_scan:
        work_args = [
            (fp, category, min_size_bytes, hash_algorithm, exclude_patterns)
            for fp in files_to_scan
        ]
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            futures = [
                executor.submit(_scan_and_hash_file, args)
                for args in work_args
            ]
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        new_files.append(FileInfo(**result))
                except Exception:
                    pass

    cached_paths = set(cached_files.keys())
    removed_count = len(cached_paths - current_paths)

    return ScanResult(
        new_files=new_files,
        unchanged_count=len(unchanged_files),
        removed_count=removed_count,
        total_size=total_size,
    )


def scan_folder_parallel(
    root_path: str,
    category: str = "unknown",
    include_extensions: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
    min_size_bytes: int = 0,
    hash_algorithm: str = "xxhash",
    num_workers: int = NUM_WORKERS,
) -> List[FileInfo]:
    """Scan a folder (non-incremental, for backwards compatibility)."""
    result = scan_folder_incremental(
        root_path=root_path,
        category=category,
        cached_files={},
        include_extensions=include_extensions,
        exclude_patterns=exclude_patterns,
        min_size_bytes=min_size_bytes,
        hash_algorithm=hash_algorithm,
        num_workers=num_workers,
    )
    return result.new_files
