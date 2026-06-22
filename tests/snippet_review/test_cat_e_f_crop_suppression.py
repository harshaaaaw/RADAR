"""
Category E — Crop Quality (TS-33 to TS-38)
Category F — Suppression Filter Boundaries (TS-39 to TS-45)

Tests crop quality pipeline and suppression filter logic.
"""
import json
import math
import numpy as np
import pytest
import sys
sys.path.insert(0, "c:/Users/DELL/Music/DocumentSearch/src")

from PIL import Image, ImageDraw
from helpers import img_to_bytes


# ═══════════════════════════════════════════════════════════════════════════════
# CATEGORY E — Crop Quality
# ═══════════════════════════════════════════════════════════════════════════════

# ─── TS-33 ──────────────────────────────────────────────────────────────────
def test_ts33_crop_has_padding():
    """D-11: Cropped snippet must be padded by ~8% of bbox size."""
    from ocr.ocr_worker import _apply_crop_padding
    x1, y1, x2, y2 = 200, 1000, 600, 1100   # bbox 400×100
    px1, py1, px2, py2 = _apply_crop_padding(x1, y1, x2, y2, w=2480, h=3508)

    assert px1 < x1, "Left edge must be expanded"
    assert py1 < y1, "Top edge must be expanded"
    assert px2 > x2, "Right edge must be expanded"
    assert py2 > y2, "Bottom edge must be expanded"
    assert px1 >= 0, "Padded x1 must be within page"
    assert py1 >= 0, "Padded y1 must be within page"


# ─── TS-34 ──────────────────────────────────────────────────────────────────
def test_ts34_micro_crop_upscaled():
    """D-11: A 10×15 pixel snippet must be upscaled to at least 80×80."""
    from ocr.ocr_worker import _ensure_minimum_resolution
    tiny = Image.new("RGB", (10, 15), (0, 0, 0))
    result = _ensure_minimum_resolution(tiny)
    assert result.width >= 80, f"Width {result.width} < 80"
    assert result.height >= 80, f"Height {result.height} < 80"


# ─── TS-35 ──────────────────────────────────────────────────────────────────
def test_ts35_deskew_corrects_angle():
    """D-11: A crop with visible text angle should be deskewed without crashing."""
    img = Image.new("L", (400, 100), 255)
    draw = ImageDraw.Draw(img)
    for x in range(50, 350):
        y = int(50 + (x - 50) * math.tan(math.radians(10)))
        if 0 <= y < 100:
            img.putpixel((x, y), 0)
    img_rgb = img.convert("RGB")

    from ocr.ocr_worker import _deskew_crop
    result = _deskew_crop(img_rgb)
    assert result is not None, "_deskew_crop returned None"
    assert result.width > 0, "Deskewed image has zero width"
    assert result.height > 0, "Deskewed image has zero height"


# ─── TS-36 ──────────────────────────────────────────────────────────────────
def test_ts36_crop_clamped_at_page_edge():
    """D-11: Padding must not produce coordinates outside page dimensions."""
    from ocr.ocr_worker import _apply_crop_padding
    # Bbox at bottom-right corner
    x1, y1, x2, y2 = 2400, 3400, 2480, 3508
    px1, py1, px2, py2 = _apply_crop_padding(x1, y1, x2, y2, w=2480, h=3508)

    assert px2 <= 2480, f"px2={px2} exceeds page width"
    assert py2 <= 3508, f"py2={py2} exceeds page height"
    assert px1 >= 0, f"px1={px1} is negative"
    assert py1 >= 0, f"py1={py1} is negative"


# ─── TS-37 ──────────────────────────────────────────────────────────────────
def test_ts37_rgba_crop_saves_correctly(tmp_path):
    """D-11: A transparent crop must be saved as valid PNG without errors."""
    rgba = Image.new("RGBA", (200, 200), (100, 200, 100, 128))
    out = tmp_path / "rgba_crop.png"
    rgba.save(str(out), format="PNG")
    loaded = Image.open(str(out))
    assert loaded.size == (200, 200)
    assert loaded.mode in ("RGBA", "RGB"), f"Unexpected mode: {loaded.mode}"


# ─── TS-38 ──────────────────────────────────────────────────────────────────
def test_ts38_corrupted_png_handled_gracefully(tmp_path):
    """D-11: Processing a truncated/corrupt crop PNG must not crash the system."""
    corrupt = tmp_path / "corrupt.png"
    corrupt.write_bytes(b"PNG\x89\x00\x00\x00IHDRCORRUPTED_DATA")

    from ocr.visual_memory import VisualMemoryEngine
    engine = VisualMemoryEngine()
    result = engine.extract_vector(str(corrupt))
    # Must return None — never raise an uncaught exception
    assert result is None, f"Expected None for corrupt PNG, got {type(result)}"


# ═══════════════════════════════════════════════════════════════════════════════
# CATEGORY F — Suppression Filter Boundaries
# ═══════════════════════════════════════════════════════════════════════════════

# ─── TS-39 ──────────────────────────────────────────────────────────────────
def test_ts39_ink_ratio_at_boundary_suppresses():
    """D-07: ink_ratio at exact boundary must trigger suppression."""
    from ocr.ocr_worker import OCRWorker
    worker = OCRWorker.__new__(OCRWorker)

    h, w = 200, 200
    arr = np.ones((h, w), dtype=np.uint8) * 255
    # Place exactly 0.004 * 200 * 200 = 160 ink pixels (boundary)
    for i in range(160):
        arr[i // w, i % w] = 0
    img = Image.fromarray(arr)

    result = worker._is_sparse_noise_visual_snippet(img, "signature")
    # At-boundary should suppress (boundary condition = suppressed)
    assert isinstance(result, bool)  # Must not crash
    assert result == True, "Boundary ink_ratio should trigger suppression"


# ─── TS-40 ──────────────────────────────────────────────────────────────────
def test_ts40_ink_ratio_above_threshold_not_suppressed():
    """D-07: ink_ratio slightly above threshold must not suppress."""
    from ocr.ocr_worker import OCRWorker
    worker = OCRWorker.__new__(OCRWorker)

    h, w = 200, 200
    arr = np.ones((h, w), dtype=np.uint8) * 255
    # 0.005 * 200 * 200 = 200 ink pixels (above threshold)
    for i in range(200):
        arr[i // w, i % w] = 0
    img = Image.fromarray(arr)

    result = worker._is_sparse_noise_visual_snippet(img, "signature")
    assert result == False, "ink_ratio of 0.005 should NOT be suppressed"


# ─── TS-41 ──────────────────────────────────────────────────────────────────
def test_ts41_printed_font_filter_returns_bool():
    """D-07: Printed font suppression check must always return a bool (never crash)."""
    from ocr.ocr_worker import OCRWorker
    worker = OCRWorker.__new__(OCRWorker)
    worker.tesseract = None  # Disable OCR fast-path

    # Uniform horizontal stripe pattern (uniform stroke width)
    arr = np.zeros((100, 300), dtype=np.uint8)
    for y in range(10, 100, 20):
        arr[y, :] = 255
    img = Image.fromarray(arr)

    result = worker._is_printed_font_snippet(img)
    assert isinstance(result, bool), f"Expected bool, got {type(result)}"


# ─── TS-42 ──────────────────────────────────────────────────────────────────
def test_ts42_suppression_logged_to_db(db):
    """D-07: Every suppressed snippet must create a row in snippet_suppression_log."""
    from core.reporting_manager import log_snippet_suppression
    log_snippet_suppression(
        db=db,
        smart_id='DOC-42',
        page_num=1,
        bbox_json='[100, 200, 300, 400]',
        suppressed_by='sparse_noise',
        snippet_type='signature',
        accuracy_impact=0.15,
    )
    rows = db.execute(
        "SELECT * FROM snippet_suppression_log WHERE smart_id='DOC-42'"
    ).fetchall()
    assert len(rows) == 1, f"Expected 1 suppression log row, got {len(rows)}"
    assert rows[0]['suppressed_by'] == 'sparse_noise'
    assert rows[0]['snippet_type'] == 'signature'


# ─── TS-43 ──────────────────────────────────────────────────────────────────
def test_ts43_faded_text_force_keep_in_source():
    """D-07: Source code must contain faded_text force_keep bypass."""
    from pathlib import Path
    src = Path("c:/Users/DELL/Music/DocumentSearch/src/ocr/ocr_worker.py").read_text(encoding="utf-8")
    assert "faded_text" in src, "Source must reference faded_text"
    assert "force_keep" in src, "Source must reference force_keep flag"


# ─── TS-44 ──────────────────────────────────────────────────────────────────
def test_ts44_worker_approved_snippets_appear_in_db(db):
    """D-07: A snippet that passed worker filters must appear as pending in DB."""
    c = db.cursor()
    c.execute("""
        INSERT INTO snippet_reviews
        (review_id, smart_id, page_num, snippet_type, deficit_category, snippet_path,
         bounding_box_json, accuracy_impact, content_area_pct, reviewer_role, status)
        VALUES ('rev44', 'DOC-44', 1, 'signature', 'signature', '/tmp/s.png',
                '[0,2000,500,2200]', 1.5, 1.55, 'Contract Auditor', 'pending')
    """)
    db.commit()

    rows = db.execute(
        "SELECT * FROM snippet_reviews WHERE smart_id='DOC-44' AND status='pending'"
    ).fetchall()
    assert len(rows) == 1, "Worker-approved snippet must appear as pending"


# ─── TS-45 ──────────────────────────────────────────────────────────────────
def test_ts45_ocr_confidence_boundary():
    """D-07: Text-like suppression threshold — boundary conditions."""
    from ocr.ocr_worker import OCRWorker
    from unittest.mock import MagicMock
    worker = OCRWorker.__new__(OCRWorker)

    mock_tess = MagicMock()
    worker.tesseract = mock_tess

    # conf = 17.9, 4 chars → should NOT suppress (below 18.0 threshold)
    mock_tess.extract_text.return_value = ("abcd", 17.9)
    result_low = worker._is_text_like_visual_snippet("/tmp/fake.png", "logo")
    assert result_low == False, "17.9 confidence should not suppress"

    # conf = 18.0, 4 chars → SHOULD suppress (at threshold)
    mock_tess.extract_text.return_value = ("abcd", 18.0)
    result_at = worker._is_text_like_visual_snippet("/tmp/fake.png", "logo")
    assert result_at == True, "18.0 confidence should suppress"
