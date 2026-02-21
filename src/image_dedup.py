"""Backward-compatible re-exports — use src.analysis.image_dedup instead."""
from src.analysis.image_dedup import (  # noqa: F401
    IMAGE_EXTENSIONS,
    is_image,
    compute_phash,
    compute_ahash,
    hamming_distance,
    find_similar_images,
    find_similar_images_from_db,
)
