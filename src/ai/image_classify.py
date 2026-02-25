"""
Image classification using metadata heuristics.

Classifies images into categories:
  - screenshot: screen captures, UI recordings
  - photo: camera photos (EXIF-based)
  - document: scanned documents, receipts
  - diagram: charts, flowcharts, architecture diagrams
  - icon: small icons, favicons, logos
  - meme: image macros, social media images
  - other: uncategorized

Works offline using filename patterns, dimensions, file size, and EXIF metadata.
No AI API calls needed for basic classification.
"""

import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif",
    ".svg", ".ico", ".heic", ".heif", ".avif", ".raw", ".cr2", ".nef",
}


@dataclass
class ImageClassification:
    """Classification result for a single image."""
    path: str
    category: str
    confidence: float
    reasons: list[str]

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "category": self.category,
            "confidence": self.confidence,
            "reasons": self.reasons,
        }


# ------------------------------------------------------------------
# Filename-based heuristics
# ------------------------------------------------------------------

_SCREENSHOT_PATTERNS = [
    re.compile(r"screen\s*shot", re.IGNORECASE),
    re.compile(r"Screenshot\s+\d{4}", re.IGNORECASE),
    re.compile(r"Capture[d]?\s+\d", re.IGNORECASE),
    re.compile(r"Screen\s*Recording", re.IGNORECASE),
    re.compile(r"CleanShot", re.IGNORECASE),
    re.compile(r"Snip\s*\d", re.IGNORECASE),
    re.compile(r"snagit", re.IGNORECASE),
    re.compile(r"grab[-_]", re.IGNORECASE),
]

_PHOTO_PATTERNS = [
    re.compile(r"IMG_\d{4}", re.IGNORECASE),
    re.compile(r"DSC[_N]\d{4}", re.IGNORECASE),
    re.compile(r"DCIM", re.IGNORECASE),
    re.compile(r"Photo\s+\d", re.IGNORECASE),
    re.compile(r"P\d{7,}", re.IGNORECASE),
    re.compile(r"\d{4}-\d{2}-\d{2}\s+\d{2}\.\d{2}\.\d{2}", re.IGNORECASE),
]

_DOCUMENT_PATTERNS = [
    re.compile(r"scan", re.IGNORECASE),
    re.compile(r"receipt", re.IGNORECASE),
    re.compile(r"invoice", re.IGNORECASE),
    re.compile(r"contract", re.IGNORECASE),
    re.compile(r"document", re.IGNORECASE),
    re.compile(r"passport", re.IGNORECASE),
    re.compile(r"license", re.IGNORECASE),
    re.compile(r"statement", re.IGNORECASE),
]

_DIAGRAM_PATTERNS = [
    re.compile(r"diagram", re.IGNORECASE),
    re.compile(r"flowchart", re.IGNORECASE),
    re.compile(r"architecture", re.IGNORECASE),
    re.compile(r"wireframe", re.IGNORECASE),
    re.compile(r"mockup", re.IGNORECASE),
    re.compile(r"schema", re.IGNORECASE),
    re.compile(r"chart", re.IGNORECASE),
    re.compile(r"graph[-_]", re.IGNORECASE),
]

_ICON_PATTERNS = [
    re.compile(r"icon", re.IGNORECASE),
    re.compile(r"favicon", re.IGNORECASE),
    re.compile(r"logo", re.IGNORECASE),
    re.compile(r"badge", re.IGNORECASE),
    re.compile(r"avatar", re.IGNORECASE),
]

_MEME_PATTERNS = [
    re.compile(r"meme", re.IGNORECASE),
    re.compile(r"reaction", re.IGNORECASE),
    re.compile(r"funny", re.IGNORECASE),
    re.compile(r"lol", re.IGNORECASE),
]


def _match_patterns(name: str, patterns: list) -> bool:
    return any(p.search(name) for p in patterns)


# ------------------------------------------------------------------
# Size-based heuristics
# ------------------------------------------------------------------

def _classify_by_size(size_bytes: int, extension: str) -> Optional[tuple[str, float, str]]:
    """Classify based on file size heuristics."""
    if extension == ".ico" or size_bytes < 10_000:
        return ("icon", 0.7, "very small image file")
    if extension in (".svg",) and size_bytes < 50_000:
        return ("icon", 0.6, "small SVG file")
    if extension in (".raw", ".cr2", ".nef"):
        return ("photo", 0.85, "RAW camera format")
    if extension in (".heic", ".heif"):
        return ("photo", 0.8, "HEIC photo format")
    return None


# ------------------------------------------------------------------
# Main classifier
# ------------------------------------------------------------------

def classify_image(
    path: str,
    name: str,
    extension: str,
    size_bytes: int,
) -> ImageClassification:
    """Classify a single image file based on metadata heuristics.

    Args:
        path: Full file path.
        name: Filename.
        extension: File extension (lowercase, with dot).
        size_bytes: File size.

    Returns:
        ImageClassification with category, confidence, and reasoning.
    """
    reasons = []
    ext = extension.lower()

    # 1. Filename pattern matching (highest confidence)
    if _match_patterns(name, _SCREENSHOT_PATTERNS):
        reasons.append("filename matches screenshot pattern")
        return ImageClassification(path, "screenshot", 0.9, reasons)

    if _match_patterns(name, _PHOTO_PATTERNS):
        reasons.append("filename matches camera photo pattern")
        return ImageClassification(path, "photo", 0.85, reasons)

    if _match_patterns(name, _DOCUMENT_PATTERNS):
        reasons.append("filename suggests scanned document")
        return ImageClassification(path, "document", 0.8, reasons)

    if _match_patterns(name, _DIAGRAM_PATTERNS):
        reasons.append("filename suggests diagram or chart")
        return ImageClassification(path, "diagram", 0.8, reasons)

    if _match_patterns(name, _ICON_PATTERNS):
        reasons.append("filename suggests icon or logo")
        return ImageClassification(path, "icon", 0.8, reasons)

    if _match_patterns(name, _MEME_PATTERNS):
        reasons.append("filename suggests meme or reaction image")
        return ImageClassification(path, "meme", 0.6, reasons)

    # 2. Size and format heuristics
    size_result = _classify_by_size(size_bytes, ext)
    if size_result:
        cat, conf, reason = size_result
        reasons.append(reason)
        return ImageClassification(path, cat, conf, reasons)

    # 3. Path-based heuristics
    path_lower = path.lower()
    if "/screenshots/" in path_lower or "\\screenshots\\" in path_lower:
        reasons.append("found in screenshots directory")
        return ImageClassification(path, "screenshot", 0.8, reasons)
    if "/photos/" in path_lower or "/camera/" in path_lower or "/dcim/" in path_lower:
        reasons.append("found in photos/camera directory")
        return ImageClassification(path, "photo", 0.75, reasons)
    if "/documents/" in path_lower or "/scans/" in path_lower:
        reasons.append("found in documents/scans directory")
        return ImageClassification(path, "document", 0.6, reasons)
    if "/icons/" in path_lower or "/assets/" in path_lower:
        reasons.append("found in icons/assets directory")
        return ImageClassification(path, "icon", 0.6, reasons)

    # 4. Size-range guessing
    if size_bytes > 2_000_000 and ext in (".jpg", ".jpeg", ".png"):
        reasons.append("large JPEG/PNG likely a photo")
        return ImageClassification(path, "photo", 0.5, reasons)

    if 50_000 < size_bytes < 500_000 and ext == ".png":
        reasons.append("mid-size PNG could be screenshot or diagram")
        return ImageClassification(path, "screenshot", 0.4, reasons)

    reasons.append("no strong classification signals found")
    return ImageClassification(path, "other", 0.3, reasons)


def classify_images_in_db(db, limit: int = 500) -> list[ImageClassification]:
    """Classify all image files in the database.

    Args:
        db: FileDatabase instance.
        limit: Maximum images to classify.

    Returns:
        List of ImageClassification results.
    """
    ext_list = ", ".join(f"'{e}'" for e in IMAGE_EXTENSIONS)
    rows = db.conn.execute(f"""
        SELECT path, name, extension, size_bytes
        FROM files
        WHERE LOWER(extension) IN ({ext_list})
        ORDER BY size_bytes DESC
        LIMIT ?
    """, [limit]).fetchall()

    return [
        classify_image(path=r[0], name=r[1], extension=r[2], size_bytes=r[3])
        for r in rows
    ]


def image_classification_summary(db, limit: int = 500) -> dict:
    """Return aggregate image classification stats."""
    results = classify_images_in_db(db, limit=limit)

    category_counts: dict[str, int] = {}
    for r in results:
        category_counts[r.category] = category_counts.get(r.category, 0) + 1

    return {
        "total_images": len(results),
        "categories": category_counts,
        "classifications": [r.to_dict() for r in results],
    }
