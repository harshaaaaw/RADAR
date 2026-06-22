import pytest
import sqlite3
import numpy as np
from PIL import Image, ImageDraw
from pathlib import Path
import json, io, re, sys

# Ensure src/ and tests/snippet_review/ are on sys.path for all test imports
_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).parent))


# ─── DB Fixture ────────────────────────────────────────────────────────────────
@pytest.fixture
def db(tmp_path):
    """In-memory SQLite with full redesigned schema."""
    conn = sqlite3.connect(tmp_path / "audit.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE file_state (
        file_key TEXT PRIMARY KEY,
        smart_id TEXT,
        file_name TEXT,
        extraction_accuracy REAL DEFAULT 0.0,
        enhanced_accuracy REAL DEFAULT 0.0,
        approval_status TEXT DEFAULT 'Pending Review',
        current_status TEXT DEFAULT 'pending',
        processed_on TEXT,
        file_type TEXT,
        file_size INTEGER,
        file_path TEXT,
        pipeline_type TEXT,
        accuracy_loss_json TEXT,
        page_metrics_json TEXT,
        accuracy_tier TEXT
    );
    CREATE TABLE snippet_reviews (
        review_id TEXT PRIMARY KEY,
        smart_id TEXT NOT NULL,
        page_num INTEGER NOT NULL,
        snippet_type TEXT NOT NULL,
        deficit_category TEXT DEFAULT 'unknown',
        snippet_path TEXT NOT NULL,
        bounding_box_json TEXT NOT NULL,
        norm_bbox_json TEXT,
        accuracy_impact REAL NOT NULL,
        content_area_pct REAL DEFAULT 0.0,
        reviewer_role TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        feature_vector_path TEXT,
        reviewed_at TEXT,
        reviewed_by TEXT,
        review_reason TEXT,
        transcription_text TEXT,
        rejection_category TEXT,
        file_size_bytes INTEGER DEFAULT 0,
        page_width_px INTEGER DEFAULT 0,
        page_height_px INTEGER DEFAULT 0,
        extracted_text TEXT
    );
    CREATE TABLE page_segmentation_breakdown (
        smart_id TEXT NOT NULL,
        page_num INTEGER NOT NULL,
        clean_text_pct REAL DEFAULT 0.0,
        faded_text_pct REAL DEFAULT 0.0,
        logo_pct REAL DEFAULT 0.0,
        stamp_pct REAL DEFAULT 0.0,
        handwritten_pct REAL DEFAULT 0.0,
        whitespace_pct REAL DEFAULT 0.0,
        noise_pct REAL DEFAULT 0.0,
        content_area_pct REAL DEFAULT 100.0,
        baseline_accuracy REAL DEFAULT 0.0,
        page_width_px INTEGER DEFAULT 0,
        page_height_px INTEGER DEFAULT 0,
        analyzed_at TEXT DEFAULT '2026-01-01T00:00:00',
        PRIMARY KEY (smart_id, page_num)
    );
    CREATE TABLE review_activity_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        review_id TEXT NOT NULL,
        smart_id TEXT NOT NULL,
        action TEXT NOT NULL,
        action_category TEXT,
        is_cancelled INTEGER DEFAULT 0,
        actor TEXT,
        reason TEXT,
        timestamp TEXT NOT NULL,
        accuracy_before REAL,
        accuracy_after REAL,
        snippet_type TEXT,
        file_name TEXT
    );
    CREATE TABLE snippet_suppression_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        smart_id TEXT NOT NULL,
        page_num INTEGER NOT NULL,
        bbox_json TEXT NOT NULL,
        suppressed_by TEXT NOT NULL,
        snippet_type TEXT NOT NULL,
        accuracy_impact REAL NOT NULL,
        suppressed_at TEXT NOT NULL
    );
    CREATE TABLE opensearch_retry_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        smart_id TEXT NOT NULL,
        review_id TEXT NOT NULL,
        payload TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        attempt_count INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        last_attempted_at TEXT
    );
    """)
    conn.commit()
    yield conn
    conn.close()


# ─── Image Generators ──────────────────────────────────────────────────────────
def make_blank_page(w=2480, h=3508, fill=255):
    """A4 at 300 DPI, default white."""
    return Image.new("RGB", (w, h), (fill, fill, fill))

def make_page_with_text(text_coverage=0.80):
    """Simulated page with black text blocks covering text_coverage % of area."""
    img = make_blank_page()
    draw = ImageDraw.Draw(img)
    h = int(3508 * text_coverage)
    draw.rectangle([200, 200, 2280, 200 + h], fill=(20, 20, 20))
    return img

def make_faded_text_page():
    """Page where printed text is very faint (gray ~200/255)."""
    img = make_blank_page()
    draw = ImageDraw.Draw(img)
    # Faded text band: gray value ~210 (nearly white, hard for Otsu)
    for y in range(300, 800, 40):
        draw.rectangle([200, y, 2200, y + 22], fill=(210, 210, 210))
    return img

def make_signature_page():
    """Page with a signature-like cursive stroke in the lower half."""
    img = make_blank_page()
    draw = ImageDraw.Draw(img)
    # Simulate cursive strokes (irregular lines in lower 30%)
    points = [(400+i*5, 2800 + int(30*np.sin(i/5))) for i in range(200)]
    draw.line(points, fill=(0, 0, 0), width=3)
    return img

def make_stamp_page():
    """Page with a circular stamp in the lower right."""
    img = make_blank_page()
    draw = ImageDraw.Draw(img)
    draw.ellipse([1800, 2800, 2200, 3200], outline=(180, 0, 0), width=8)
    # Draw simple text fallback or rectangles if text font not loaded
    draw.rectangle([1850, 2900, 2150, 3100], fill=(180, 0, 0))
    return img

def img_to_bytes(pil_img):
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return buf.getvalue()
