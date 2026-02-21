"""
Deletion manifest — tracks deleted files for recovery within a configurable window.
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

DEFAULT_MANIFEST_DIR = "~/.doc-intelligence"
MANIFEST_FILE = "deletion_manifest.json"
DEFAULT_UNDO_WINDOW_DAYS = 30


def _manifest_path(manifest_dir: Optional[str] = None) -> Path:
    base = Path(manifest_dir or DEFAULT_MANIFEST_DIR).expanduser()
    base.mkdir(parents=True, exist_ok=True)
    return base / MANIFEST_FILE


def load_manifest(manifest_dir: Optional[str] = None) -> list[dict]:
    path = _manifest_path(manifest_dir)
    if not path.exists():
        return []
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def save_manifest(entries: list[dict], manifest_dir: Optional[str] = None):
    path = _manifest_path(manifest_dir)
    with open(path, "w") as f:
        json.dump(entries, f, indent=2, default=str)


def record_deletion(
    original_path: str,
    size_bytes: int,
    content_hash: Optional[str] = None,
    reason: str = "duplicate_cleanup",
    manifest_dir: Optional[str] = None,
):
    entries = load_manifest(manifest_dir)
    entries.append({
        "original_path": original_path,
        "size_bytes": size_bytes,
        "content_hash": content_hash,
        "reason": reason,
        "deleted_at": datetime.now().isoformat(),
        "expires_at": (
            datetime.now() + timedelta(days=DEFAULT_UNDO_WINDOW_DAYS)
        ).isoformat(),
    })
    save_manifest(entries, manifest_dir)


def record_batch_deletion(
    files: list[dict],
    reason: str = "duplicate_cleanup",
    manifest_dir: Optional[str] = None,
):
    entries = load_manifest(manifest_dir)
    now = datetime.now()
    expires = now + timedelta(days=DEFAULT_UNDO_WINDOW_DAYS)
    for f in files:
        entries.append({
            "original_path": f["path"],
            "size_bytes": f.get("size_bytes", 0),
            "content_hash": f.get("content_hash"),
            "reason": reason,
            "deleted_at": now.isoformat(),
            "expires_at": expires.isoformat(),
        })
    save_manifest(entries, manifest_dir)


def get_recent_deletions(
    days: int = DEFAULT_UNDO_WINDOW_DAYS,
    manifest_dir: Optional[str] = None,
) -> list[dict]:
    entries = load_manifest(manifest_dir)
    cutoff = datetime.now() - timedelta(days=days)
    return [
        e for e in entries
        if datetime.fromisoformat(e["deleted_at"]) > cutoff
    ]


def purge_expired(manifest_dir: Optional[str] = None) -> int:
    entries = load_manifest(manifest_dir)
    now = datetime.now()
    active = [
        e for e in entries
        if datetime.fromisoformat(e["expires_at"]) > now
    ]
    removed = len(entries) - len(active)
    save_manifest(active, manifest_dir)
    return removed


def find_recoverable(
    content_hash: str,
    db=None,
    manifest_dir: Optional[str] = None,
) -> Optional[str]:
    if db is None or not content_hash:
        return None
    rows = db.conn.execute(
        "SELECT path FROM files WHERE content_hash = ? LIMIT 1",
        [content_hash],
    ).fetchall()
    if rows:
        existing_path = rows[0][0]
        if Path(existing_path).exists():
            return existing_path
    return None


def get_deletion_summary(manifest_dir: Optional[str] = None) -> dict:
    entries = load_manifest(manifest_dir)
    now = datetime.now()
    total = len(entries)
    total_bytes = sum(e.get("size_bytes", 0) for e in entries)
    active = [
        e for e in entries
        if datetime.fromisoformat(e["expires_at"]) > now
    ]
    return {
        "total_deleted": total,
        "total_bytes": total_bytes,
        "recent_count": len(active),
        "expired_count": total - len(active),
    }
