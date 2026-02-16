"""
Perceptual Image Deduplication Module
Finds near-duplicate images using perceptual hashing.
Detects resized, recompressed, and slightly modified copies.
"""

from pathlib import Path
from typing import Optional
from collections import defaultdict

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp"}


def is_image(path: str) -> bool:
    """Check if file has an image extension."""
    return Path(path).suffix.lower() in IMAGE_EXTENSIONS


def compute_phash(image_path: str) -> Optional[str]:
    """
    Compute perceptual hash of an image.

    Returns:
        Hex string of the phash, or None if the image can't be processed.
    """
    try:
        import imagehash
        from PIL import Image

        img = Image.open(image_path)
        h = imagehash.phash(img)
        return str(h)
    except Exception:
        return None


def compute_ahash(image_path: str) -> Optional[str]:
    """Compute average hash of an image."""
    try:
        import imagehash
        from PIL import Image

        img = Image.open(image_path)
        h = imagehash.average_hash(img)
        return str(h)
    except Exception:
        return None


def hamming_distance(hash1: str, hash2: str) -> int:
    """
    Compute Hamming distance between two hex hash strings.
    Lower distance = more similar images.
    """
    # Convert hex to binary
    b1 = bin(int(hash1, 16))
    b2 = bin(int(hash2, 16))
    # Pad to same length
    max_len = max(len(b1), len(b2))
    b1 = b1.zfill(max_len)
    b2 = b2.zfill(max_len)
    return sum(c1 != c2 for c1, c2 in zip(b1, b2))


def find_similar_images(
    image_paths: list[str],
    threshold: int = 10,
    hash_func: str = "phash",
) -> list[dict]:
    """
    Find groups of visually similar images.

    Args:
        image_paths: List of image file paths
        threshold: Maximum hamming distance to consider as similar (0=identical, lower=stricter)
        hash_func: Hash function to use ('phash' or 'ahash')

    Returns:
        List of groups, each containing:
        - paths: list of similar image paths
        - distance: max hamming distance within group
    """
    compute_fn = compute_phash if hash_func == "phash" else compute_ahash

    # Compute hashes for all images
    hashes = {}
    for path in image_paths:
        h = compute_fn(path)
        if h is not None:
            hashes[path] = h

    if not hashes:
        return []

    # Group similar images using Union-Find
    parent = {p: p for p in hashes}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    paths_list = list(hashes.keys())
    for i in range(len(paths_list)):
        for j in range(i + 1, len(paths_list)):
            p1, p2 = paths_list[i], paths_list[j]
            dist = hamming_distance(hashes[p1], hashes[p2])
            if dist <= threshold:
                union(p1, p2)

    # Collect groups
    groups = defaultdict(list)
    for path in paths_list:
        groups[find(path)].append(path)

    # Only return groups with 2+ images
    result = []
    for group_paths in groups.values():
        if len(group_paths) >= 2:
            # Calculate total size
            total_size = 0
            for p in group_paths:
                try:
                    total_size += Path(p).stat().st_size
                except OSError:
                    pass

            result.append({
                "paths": sorted(group_paths),
                "count": len(group_paths),
                "total_size": total_size,
                "wasted_size": total_size - (total_size // len(group_paths)),
            })

    return sorted(result, key=lambda x: x["wasted_size"], reverse=True)


def find_similar_images_from_db(db, threshold: int = 10) -> list[dict]:
    """
    Find similar images from the database.

    Args:
        db: FileDatabase instance
        threshold: Hamming distance threshold

    Returns:
        List of similar image groups
    """
    # Get all image paths from the database
    image_exts_sql = ", ".join(f"'{ext}'" for ext in IMAGE_EXTENSIONS)
    rows = db.conn.execute(f"""
        SELECT path FROM files
        WHERE extension IN ({image_exts_sql})
    """).fetchall()

    image_paths = [row[0] for row in rows]

    if not image_paths:
        return []

    return find_similar_images(image_paths, threshold=threshold)
