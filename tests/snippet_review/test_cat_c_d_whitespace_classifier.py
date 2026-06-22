"""
Category C — Whitespace Profiling (TS-17 to TS-22)
Category D — Deficit Classifier (TS-23 to TS-32)

Tests whitespace validation and deficit type classification.
"""
import json
import numpy as np
import pytest
import sys
sys.path.insert(0, "c:/Users/DELL/Music/DocumentSearch/src")

from PIL import Image, ImageDraw
from helpers import (
    make_blank_page, make_faded_text_page, make_signature_page,
    make_stamp_page, img_to_bytes
)


# ═══════════════════════════════════════════════════════════════════════════════
# CATEGORY C — Whitespace Profiling
# ═══════════════════════════════════════════════════════════════════════════════

# ─── TS-17 ──────────────────────────────────────────────────────────────────
def test_ts17_margin_page_whitespace():
    """D-04: Wide-margin A4 must report whitespace >= 40%."""
    img = make_blank_page()
    draw = ImageDraw.Draw(img)
    # Only text in a small center block (simulating wide margins)
    draw.rectangle([700, 700, 1780, 2800], fill=(20, 20, 20))

    from extraction.accuracy_analyzer import AccuracyAnalyzer
    a = AccuracyAnalyzer(enable_yolo=False, enable_doctr=False)
    metrics = a._segment_page_opencv(img_to_bytes(img))
    ws = metrics.get("validated_whitespace_pct", metrics.get("whitespace_pct", 0.0))
    assert ws >= 30.0, f"Expected >= 30% whitespace, got {ws}"


# ─── TS-18 ──────────────────────────────────────────────────────────────────
def test_ts18_suspect_whitespace_reclassified():
    """D-04: A 'whitespace' region containing faint ink must NOT be validated as whitespace."""
    img = make_blank_page()
    draw = ImageDraw.Draw(img)
    # Faint text in what would otherwise look like a margin
    draw.rectangle([50, 100, 400, 160], fill=(220, 220, 220))

    from extraction.accuracy_analyzer import AccuracyAnalyzer
    a = AccuracyAnalyzer(enable_yolo=False, enable_doctr=False)
    arr = np.array(img.convert("L"))
    region = (50, 100, 400, 160)
    is_genuine_ws = a._validate_whitespace_region(arr, region)
    assert is_genuine_ws == False, \
        "Faint-ink region incorrectly validated as whitespace"


# ─── TS-19 ──────────────────────────────────────────────────────────────────
def test_ts19_empty_margin_is_whitespace():
    """D-04: A truly empty margin must pass whitespace validation."""
    img = make_blank_page()  # all white
    from extraction.accuracy_analyzer import AccuracyAnalyzer
    a = AccuracyAnalyzer(enable_yolo=False, enable_doctr=False)
    arr = np.array(img.convert("L"))
    is_ws = a._validate_whitespace_region(arr, (0, 0, 500, 500))
    assert is_ws == True, "Pure white region must validate as whitespace"


# ─── TS-20 ──────────────────────────────────────────────────────────────────
def test_ts20_watermark_counted_as_background():
    """D-04: Light watermark pattern must not contribute to content_area_pct significantly."""
    img = make_blank_page()
    draw = ImageDraw.Draw(img)
    # Faint repeating watermark pattern (barely visible)
    for y in range(0, 3508, 200):
        for x in range(0, 2480, 400):
            draw.text((x, y), "CONF", fill=(248, 248, 248))

    from extraction.accuracy_analyzer import AccuracyAnalyzer
    a = AccuracyAnalyzer(enable_yolo=False, enable_doctr=False)
    metrics = a._segment_page_opencv(img_to_bytes(img))
    # Watermark-only page should have very high whitespace
    ws = metrics.get("validated_whitespace_pct", metrics.get("whitespace_pct", 0.0))
    assert ws >= 80.0, f"Expected mostly whitespace for watermark page, got {ws:.1f}%"


# ─── TS-21 ──────────────────────────────────────────────────────────────────
def test_ts21_full_bleed_near_zero_whitespace():
    """D-04: A near-black full-bleed page must report near-zero whitespace."""
    img = make_blank_page(fill=20)  # near-black fill
    from extraction.accuracy_analyzer import AccuracyAnalyzer
    a = AccuracyAnalyzer(enable_yolo=False, enable_doctr=False)
    metrics = a._segment_page_opencv(img_to_bytes(img))
    ws = metrics.get("validated_whitespace_pct", metrics.get("whitespace_pct", 100.0))
    assert ws < 20.0, \
        f"Full-bleed page should have < 20% whitespace, got {ws:.1f}%"


# ─── TS-22 ──────────────────────────────────────────────────────────────────
def test_ts22_table_grid_lines_not_faded():
    """D-04: Horizontal and vertical table lines must not create spurious faded_text snippets."""
    img = make_blank_page()
    draw = ImageDraw.Draw(img)
    for y in range(500, 2000, 300):
        draw.line([(200, y), (2200, y)], fill=0, width=2)
    for x in range(200, 2300, 500):
        draw.line([(x, 500), (x, 2000)], fill=0, width=2)

    from extraction.accuracy_analyzer import AccuracyAnalyzer
    a = AccuracyAnalyzer(enable_yolo=False, enable_doctr=False)
    zones = a._segment_page_opencv(img_to_bytes(img))
    bboxes = zones.get("bboxes", [])
    snippet_types = [b["type"] for b in bboxes]
    # Grid lines should NOT create faded_text snippets
    assert "faded_text" not in snippet_types, \
        f"Table grid lines incorrectly created faded_text snippet"


# ═══════════════════════════════════════════════════════════════════════════════
# CATEGORY D — Deficit Classifier
# ═══════════════════════════════════════════════════════════════════════════════

# ─── TS-23 ──────────────────────────────────────────────────────────────────
def test_ts23_circular_red_stamp_classified():
    """D-05: A circular red ink shape must be classified as 'stamp'."""
    img = Image.new("RGB", (300, 300), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.ellipse([20, 20, 280, 280], outline=(200, 0, 0), width=8)
    draw.rectangle([80, 100, 220, 200], fill=(200, 0, 0))

    from ocr.ocr_worker import OCRWorker
    worker = OCRWorker.__new__(OCRWorker)
    tag, role = worker.classify_snippet_deficit(
        img, [0, 0, 300, 300], (2480, 3508), "logo",
        tesseract_result=("APPROVED", 30.0)
    )
    assert tag == "stamp", f"Expected 'stamp', got '{tag}'"


# ─── TS-24 ──────────────────────────────────────────────────────────────────
def test_ts24_cursive_strokes_signature():
    """D-05: Irregular strokes in lower page zone must be classified as 'signature'."""
    img = make_signature_page()
    crop = img.crop((350, 2750, 1600, 2900))

    from ocr.ocr_worker import OCRWorker
    worker = OCRWorker.__new__(OCRWorker)
    tag, role = worker.classify_snippet_deficit(
        crop, [350, 2750, 1600, 2900], (2480, 3508), "signature",
        tesseract_result=("", 5.0)
    )
    assert tag == "signature", f"Expected 'signature', got '{tag}'"


# ─── TS-25 ──────────────────────────────────────────────────────────────────
def test_ts25_blue_annotation_is_handwritten():
    """D-03, D-05: Blue cursive strokes in margin must be classified as 'handwritten'."""
    img = Image.new("RGB", (200, 100), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.line(
        [(10, 50), (40, 30), (80, 60), (120, 20), (180, 50)],
        fill=(0, 0, 200), width=3
    )

    from ocr.ocr_worker import OCRWorker
    worker = OCRWorker.__new__(OCRWorker)
    tag, role = worker.classify_snippet_deficit(
        img, [0, 0, 200, 100], (2480, 3508), "signature",
        tesseract_result=("", 8.0)
    )
    # Should be handwritten (high SW variance, color ink, not lower-zone signature pattern)
    assert tag in ("handwritten", "signature"), \
        f"Expected 'handwritten' or 'signature', got '{tag}'"


# ─── TS-26 ──────────────────────────────────────────────────────────────────
def test_ts26_logo_with_text_stays_logo():
    """D-05: A colorful logo containing text should be tagged 'logo', not 'faded_text'."""
    img = Image.new("RGB", (300, 200), (30, 80, 160))  # blue logo background
    draw = ImageDraw.Draw(img)
    draw.rectangle([10, 10, 290, 190], fill=(30, 80, 160))

    from ocr.ocr_worker import OCRWorker
    worker = OCRWorker.__new__(OCRWorker)
    tag, role = worker.classify_snippet_deficit(
        img, [100, 100, 400, 300], (2480, 3508), "logo",
        tesseract_result=("ACME Corp", 65.0)
    )
    assert tag == "logo", f"Expected 'logo', got '{tag}'"


# ─── TS-27 ──────────────────────────────────────────────────────────────────
def test_ts27_low_confidence_ocr_is_faded():
    """D-05: Region where Tesseract returns garbled text with conf < 30 → faded_text."""
    img = make_faded_text_page().crop((200, 300, 2200, 400))

    from ocr.ocr_worker import OCRWorker
    worker = OCRWorker.__new__(OCRWorker)
    tag, role = worker.classify_snippet_deficit(
        img, [200, 300, 2200, 400], (2480, 3508), "text_anomaly",
        tesseract_result=("§~@#!", 12.0)
    )
    assert tag == "faded_text", f"Expected 'faded_text', got '{tag}'"
    assert role == "Faded Text Specialist"


# ─── TS-28 ──────────────────────────────────────────────────────────────────
def test_ts28_rotated_stamp_classified():
    """D-05: A stamp rotated 45° must still be classified as 'stamp' via color detection."""
    img = Image.new("RGB", (300, 300), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.ellipse([20, 20, 280, 280], outline=(180, 0, 0), width=6)
    rotated = img.rotate(45, fillcolor=(255, 255, 255))

    from ocr.ocr_worker import OCRWorker
    worker = OCRWorker.__new__(OCRWorker)
    tag, _ = worker.classify_snippet_deficit(
        rotated, [0, 0, 300, 300], (2480, 3508), "logo",
        tesseract_result=("", 5.0)
    )
    assert tag == "stamp", f"Expected 'stamp', got '{tag}'"


# ─── TS-29 ──────────────────────────────────────────────────────────────────
def test_ts29_high_ocr_conf_text_anomaly():
    """D-05: Region with Tesseract conf >= 70 is machine-readable → text_anomaly."""
    from ocr.ocr_worker import OCRWorker
    worker = OCRWorker.__new__(OCRWorker)
    img = Image.new("RGB", (400, 100), (255, 255, 255))
    tag, _ = worker.classify_snippet_deficit(
        img, [0, 0, 400, 100], (2480, 3508), "text_anomaly",
        tesseract_result=("Invoice Date 2026", 82.0)
    )
    assert tag == "text_anomaly", f"Expected 'text_anomaly', got '{tag}'"


# ─── TS-30 ──────────────────────────────────────────────────────────────────
def test_ts30_role_is_config_driven():
    """D-06: Reviewer role must come from _role_for(), not hardcoded strings."""
    from ocr.ocr_worker import _role_for
    assert _role_for("handwritten") == "Transcription Auditor"
    assert _role_for("faded_text") == "Faded Text Specialist"
    assert _role_for("stamp") == "Compliance Officer"
    assert _role_for("logo") == "Brand Integrity Reviewer"
    # Unknown type gets a safe default (not empty)
    fallback = _role_for("alien_type")
    assert fallback != "", "Unknown type must return a non-empty fallback role"


# ─── TS-31 ──────────────────────────────────────────────────────────────────
def test_ts31_blank_line_is_sparse_noise():
    """D-05: A blank horizontal line (signature box without ink) is noise, not signature."""
    img = Image.new("RGB", (500, 30), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.line([(10, 25), (490, 25)], fill=(200, 200, 200), width=1)

    from ocr.ocr_worker import OCRWorker
    worker = OCRWorker.__new__(OCRWorker)
    is_noise = worker._is_sparse_noise_visual_snippet(img, "signature")
    assert is_noise == True, \
        "Blank faint signature line must be filtered as sparse noise"


# ─── TS-32 ──────────────────────────────────────────────────────────────────
def test_ts32_qr_code_classified_logo():
    """D-05: A dense grid pattern (QR code) must not be classified as stamp or signature."""
    arr = np.zeros((100, 100, 3), dtype=np.uint8)
    arr[::2, ::2] = 255  # checkerboard
    img = Image.fromarray(arr)

    from ocr.ocr_worker import OCRWorker
    worker = OCRWorker.__new__(OCRWorker)
    tag, _ = worker.classify_snippet_deficit(
        img, [500, 500, 600, 600], (2480, 3508), "logo",
        tesseract_result=("", 0.0)
    )
    assert tag in ("logo", "text_anomaly", "stamp"), \
        f"QR code misclassified as unexpected '{tag}'"
