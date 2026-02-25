"""Tests for image classification module."""

import pytest
from src.ai.image_classify import (
    classify_image,
    ImageClassification,
    IMAGE_EXTENSIONS,
)


class TestClassifyScreenshots:
    def test_screenshot_filename_pattern(self):
        r = classify_image("/tmp/Screenshot 2024-01-01.png", "Screenshot 2024-01-01.png", ".png", 200000)
        assert r.category == "screenshot"
        assert r.confidence >= 0.8

    def test_cleanshot_pattern(self):
        r = classify_image("/tmp/CleanShot_2024.png", "CleanShot_2024.png", ".png", 150000)
        assert r.category == "screenshot"

    def test_capture_pattern(self):
        r = classify_image("/tmp/Captured 1.png", "Captured 1.png", ".png", 100000)
        assert r.category == "screenshot"

    def test_screenshots_directory(self):
        r = classify_image("/home/user/Screenshots/image.png", "image.png", ".png", 300000)
        assert r.category == "screenshot"


class TestClassifyPhotos:
    def test_img_prefix(self):
        r = classify_image("/camera/IMG_1234.jpg", "IMG_1234.jpg", ".jpg", 5000000)
        assert r.category == "photo"

    def test_dscn_prefix(self):
        r = classify_image("/photos/DSCN0001.jpg", "DSCN0001.jpg", ".jpg", 4000000)
        assert r.category == "photo"

    def test_heic_format(self):
        r = classify_image("/photos/image.heic", "image.heic", ".heic", 3000000)
        assert r.category == "photo"

    def test_raw_format(self):
        r = classify_image("/photos/image.cr2", "image.cr2", ".cr2", 25000000)
        assert r.category == "photo"

    def test_photos_directory(self):
        r = classify_image("/home/user/Photos/vacation.jpg", "vacation.jpg", ".jpg", 4000000)
        assert r.category == "photo"

    def test_large_jpeg_likely_photo(self):
        r = classify_image("/tmp/random.jpg", "random.jpg", ".jpg", 5000000)
        assert r.category == "photo"


class TestClassifyDocuments:
    def test_scan_filename(self):
        r = classify_image("/docs/scan_001.pdf", "scan_001.pdf", ".pdf", 500000)
        assert r.category == "document"

    def test_receipt_filename(self):
        r = classify_image("/docs/receipt_2024.png", "receipt_2024.png", ".png", 200000)
        assert r.category == "document"

    def test_invoice_filename(self):
        r = classify_image("/docs/invoice.png", "invoice.png", ".png", 300000)
        assert r.category == "document"


class TestClassifyDiagrams:
    def test_diagram_filename(self):
        r = classify_image("/docs/architecture-diagram.png", "architecture-diagram.png", ".png", 100000)
        assert r.category == "diagram"

    def test_flowchart_filename(self):
        r = classify_image("/docs/flowchart.png", "flowchart.png", ".png", 80000)
        assert r.category == "diagram"

    def test_wireframe_filename(self):
        r = classify_image("/docs/wireframe_v2.png", "wireframe_v2.png", ".png", 60000)
        assert r.category == "diagram"


class TestClassifyIcons:
    def test_icon_filename(self):
        r = classify_image("/assets/icon_home.png", "icon_home.png", ".png", 5000)
        assert r.category == "icon"

    def test_favicon(self):
        r = classify_image("/web/favicon.ico", "favicon.ico", ".ico", 2000)
        assert r.category == "icon"

    def test_small_svg(self):
        r = classify_image("/assets/logo.svg", "logo.svg", ".svg", 3000)
        assert r.category == "icon"

    def test_very_small_file(self):
        r = classify_image("/tmp/tiny.png", "tiny.png", ".png", 500)
        assert r.category == "icon"


class TestClassifyOther:
    def test_unknown_returns_other(self):
        r = classify_image("/tmp/mystery.png", "mystery.png", ".png", 30000)
        assert r.category in ("screenshot", "other")  # mid-size PNG

    def test_low_confidence_for_unknown(self):
        r = classify_image("/tmp/x.bmp", "x.bmp", ".bmp", 50000)
        assert r.confidence <= 0.5


class TestImageClassificationOutput:
    def test_has_reasons(self):
        r = classify_image("/tmp/Screenshot.png", "Screenshot.png", ".png", 200000)
        assert len(r.reasons) >= 1

    def test_to_dict(self):
        r = classify_image("/tmp/test.jpg", "test.jpg", ".jpg", 100000)
        d = r.to_dict()
        assert "path" in d
        assert "category" in d
        assert "confidence" in d
        assert "reasons" in d

    def test_image_extensions_set(self):
        assert ".jpg" in IMAGE_EXTENSIONS
        assert ".png" in IMAGE_EXTENSIONS
        assert ".svg" in IMAGE_EXTENSIONS
        assert ".heic" in IMAGE_EXTENSIONS
        assert ".txt" not in IMAGE_EXTENSIONS
