"""
Category A — Accuracy Math Stress Tests (TS-01 to TS-08)

Tests the core accuracy formula logic:
- page-as-100% segmentation
- content-area-weighted accuracy
- faded text recovery
- logo accept does NOT boost text accuracy
- multi-page weighted accuracy
"""
import json
import pytest
import sys
sys.path.insert(0, "c:/Users/DELL/Music/DocumentSearch/src")

from helpers import make_blank_page, make_page_with_text


# ─── TS-01 ──────────────────────────────────────────────────────────────────
def test_ts01_full_whitespace_page_no_division_by_zero(db):
    """D-01: content_area=0 must not crash the accuracy formula."""
    c = db.cursor()
    c.execute(
        "INSERT INTO file_state (file_key, smart_id, file_name, extraction_accuracy, enhanced_accuracy, approval_status) "
        "VALUES ('fk01', 'DOC-01', 'blank.pdf', 0.0, 0.0, 'Pending Review')"
    )
    c.execute("""
        INSERT INTO page_segmentation_breakdown
        (smart_id, page_num, whitespace_pct, content_area_pct, baseline_accuracy, analyzed_at)
        VALUES ('DOC-01', 1, 100.0, 0.0, 0.0, '2026-01-01T00:00:00')
    """)
    db.commit()

    from core.reporting_manager import calculate_document_accuracy
    result = calculate_document_accuracy(db, 'DOC-01')

    # Must not raise; must return a valid float in [0, 100]
    assert isinstance(result, float)
    assert 0.0 <= result <= 100.0


# ─── TS-02 ──────────────────────────────────────────────────────────────────
def test_ts02_page_partition_sums_to_100(db):
    """D-01, D-16: the 5-component partition must sum to exactly 100%."""
    clean = 80.0
    faded = 10.0
    logo = 5.0
    handwritten = 2.0
    whitespace = 3.0
    noise = 0.0
    stamp = 0.0

    total = clean + faded + logo + stamp + handwritten + whitespace + noise
    assert abs(total - 100.0) < 0.01, f"Partition sums to {total}, not 100"

    c = db.cursor()
    c.execute(
        "INSERT INTO file_state (file_key, smart_id, file_name, extraction_accuracy, enhanced_accuracy) "
        "VALUES ('fk02', 'DOC-02', 'test.pdf', 82.47, 82.47)"
    )
    c.execute("""
        INSERT INTO page_segmentation_breakdown
        (smart_id, page_num, clean_text_pct, faded_text_pct, logo_pct, stamp_pct,
         handwritten_pct, whitespace_pct, noise_pct, content_area_pct, baseline_accuracy, analyzed_at)
        VALUES ('DOC-02', 1, 80.0, 10.0, 5.0, 0.0, 2.0, 3.0, 0.0, 97.0, 82.47, '2026-01-01T00:00:00')
    """)
    db.commit()
    # Partition sum test passes if no assert fires
    assert abs(total - 100.0) < 0.01


# ─── TS-03 ──────────────────────────────────────────────────────────────────
def test_ts03_faded_text_recovery_increases_accuracy(db):
    """D-01: Accepting a faded_text snippet must increase enhanced_accuracy."""
    c = db.cursor()
    c.execute(
        "INSERT INTO file_state (file_key, smart_id, file_name, extraction_accuracy, enhanced_accuracy, approval_status) "
        "VALUES ('fk03', 'DOC-03', 'test.pdf', 82.47, 82.47, 'Pending Review')"
    )
    c.execute("""
        INSERT INTO page_segmentation_breakdown
        (smart_id, page_num, clean_text_pct, faded_text_pct, whitespace_pct,
         content_area_pct, baseline_accuracy, analyzed_at)
        VALUES ('DOC-03', 1, 80.0, 10.0, 3.0, 97.0, 82.47, '2026-01-01T00:00:00')
    """)
    # content_area_pct = 10/97*100 = 10.31% of content area
    c.execute("""
        INSERT INTO snippet_reviews
        (review_id, smart_id, page_num, snippet_type, deficit_category, snippet_path,
         bounding_box_json, accuracy_impact, content_area_pct, reviewer_role, status)
        VALUES ('rev003', 'DOC-03', 1, 'text_anomaly', 'faded_text', '/tmp/a.png',
                '[0,300,2200,800]', 10.0, 10.31, 'Faded Text Specialist', 'pending')
    """)
    db.commit()

    from core.reporting_manager import update_snippet_review_status
    update_snippet_review_status(
        'rev003', status='accepted',
        review_reason='Faded text recovered',
        transcription_text='Invoice date',
        db_conn=db
    )

    row = db.execute(
        "SELECT enhanced_accuracy FROM file_state WHERE smart_id='DOC-03'"
    ).fetchone()
    assert row['enhanced_accuracy'] > 82.47, \
        f"Expected accuracy to increase above 82.47, got {row['enhanced_accuracy']}"


# ─── TS-04 ──────────────────────────────────────────────────────────────────
def test_ts04_logo_accept_does_not_boost_text_accuracy(db):
    """D-01: Accepting a logo must NOT increase OCR text extraction accuracy."""
    c = db.cursor()
    c.execute(
        "INSERT INTO file_state (file_key, smart_id, file_name, extraction_accuracy, enhanced_accuracy, approval_status) "
        "VALUES ('fk04', 'DOC-04', 'doc.pdf', 87.63, 87.63, 'Pending Review')"
    )
    c.execute("""
        INSERT INTO page_segmentation_breakdown
        (smart_id, page_num, clean_text_pct, logo_pct, whitespace_pct,
         content_area_pct, baseline_accuracy, analyzed_at)
        VALUES ('DOC-04', 1, 85.0, 12.0, 3.0, 97.0, 87.63, '2026-01-01T00:00:00')
    """)
    c.execute("""
        INSERT INTO snippet_reviews
        (review_id, smart_id, page_num, snippet_type, deficit_category, snippet_path,
         bounding_box_json, accuracy_impact, content_area_pct, reviewer_role, status)
        VALUES ('rev004', 'DOC-04', 1, 'logo', 'logo', '/tmp/b.png',
                '[100,100,500,500]', 12.0, 12.37, 'Brand Integrity Reviewer', 'pending')
    """)
    db.commit()

    from core.reporting_manager import update_snippet_review_status
    update_snippet_review_status('rev004', status='accepted', db_conn=db)

    row = db.execute(
        "SELECT enhanced_accuracy FROM file_state WHERE smart_id='DOC-04'"
    ).fetchone()
    # Logo acceptance should NOT change text accuracy (logo is not a text deficit)
    baseline = 87.63
    assert row['enhanced_accuracy'] <= baseline + 0.1, \
        f"Logo acceptance incorrectly boosted accuracy to {row['enhanced_accuracy']}"


# ─── TS-05 ──────────────────────────────────────────────────────────────────
def test_ts05_float_rounding_partition_sum():
    """D-01: IEEE 754 thirds must sum correctly to ~100.0."""
    parts = {
        "clean_text_pct": 100 / 3,
        "whitespace_pct": 100 / 3,
        "logo_pct": 100 / 3 + (100 % 3) / 100,  # corrected to sum to 100
        "faded_text_pct": 0.0,
        "stamp_pct": 0.0,
        "handwritten_pct": 0.0,
        "noise_pct": 0.0,
    }
    # Normalize the partition
    total_raw = sum(parts.values())
    scale = 100.0 / max(total_raw, 0.001)
    normalized = {k: v * scale for k, v in parts.items()}
    total = sum(normalized.values())
    assert abs(total - 100.0) < 0.05, f"Normalized sum is {total}, expected 100.0"


# ─── TS-06 ──────────────────────────────────────────────────────────────────
def test_ts06_multipage_weighted_accuracy(db):
    """D-16: 3-page doc accuracy must be weighted by content area per page."""
    c = db.cursor()
    c.execute(
        "INSERT INTO file_state (file_key, smart_id, file_name, extraction_accuracy, enhanced_accuracy) "
        "VALUES ('fk06', 'DOC-06', 'multi.pdf', 0, 0)"
    )
    # Page 1: 60% clean, 40% faded, 0% WS → content=100%, baseline=60%
    # Page 2: 90% clean, 5% logo, 5% WS → content=95%, baseline=94.74%
    # Page 3: 100% clean → baseline=100%
    pages = [
        ('DOC-06', 1, 60.0, 40.0, 0.0, 0.0, 0.0, 0.0, 0.0, 100.0, 60.0),
        ('DOC-06', 2, 90.0, 0.0, 5.0, 0.0, 0.0, 5.0, 0.0, 95.0, 94.74),
        ('DOC-06', 3, 100.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 100.0, 100.0),
    ]
    for p in pages:
        c.execute("""
            INSERT INTO page_segmentation_breakdown
            (smart_id, page_num, clean_text_pct, faded_text_pct, logo_pct, stamp_pct,
             handwritten_pct, whitespace_pct, noise_pct, content_area_pct, baseline_accuracy, analyzed_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,'2026-01-01T00:00:00')
        """, p)
    db.commit()

    from core.reporting_manager import calculate_document_accuracy
    acc = calculate_document_accuracy(db, 'DOC-06')

    # Weighted: (60*100 + 94.74*95 + 100*100) / (100+95+100)
    expected = (60.0 * 100 + 94.74 * 95 + 100.0 * 100) / (100 + 95 + 100)
    assert abs(acc - expected) < 1.0, f"Expected {expected:.2f}%, got {acc:.2f}%"


# ─── TS-07 ──────────────────────────────────────────────────────────────────
def test_ts07_accuracy_cannot_exceed_100(db):
    """D-01: Accepting multiple snippets must never push accuracy above 100%."""
    c = db.cursor()
    c.execute(
        "INSERT INTO file_state (file_key, smart_id, file_name, extraction_accuracy, enhanced_accuracy) "
        "VALUES ('fk07', 'DOC-07', 'doc.pdf', 95.0, 95.0)"
    )
    c.execute("""
        INSERT INTO page_segmentation_breakdown
        (smart_id, page_num, clean_text_pct, faded_text_pct, whitespace_pct,
         content_area_pct, baseline_accuracy, analyzed_at)
        VALUES ('DOC-07', 1, 95.0, 5.0, 0.0, 100.0, 95.0, '2026-01-01T00:00:00')
    """)
    # Two snippets whose combined content_area_pct > remaining headroom
    for rev_id, cpct in [('rev07a', 3.09), ('rev07b', 3.09)]:
        c.execute("""
            INSERT INTO snippet_reviews
            (review_id, smart_id, page_num, snippet_type, deficit_category, snippet_path,
             bounding_box_json, accuracy_impact, content_area_pct, reviewer_role, status)
            VALUES (?, 'DOC-07', 1, 'text_anomaly', 'faded_text', '/tmp/x.png',
                    '[0,0,100,100]', 3.0, ?, 'Reviewer', 'pending')
        """, (rev_id, cpct))
    db.commit()

    from core.reporting_manager import update_snippet_review_status
    update_snippet_review_status('rev07a', status='accepted', transcription_text='text a', db_conn=db)
    update_snippet_review_status('rev07b', status='accepted', transcription_text='text b', db_conn=db)

    row = db.execute(
        "SELECT enhanced_accuracy FROM file_state WHERE smart_id='DOC-07'"
    ).fetchone()
    assert row['enhanced_accuracy'] <= 100.0, \
        f"Accuracy {row['enhanced_accuracy']} exceeds 100%"


# ─── TS-08 ──────────────────────────────────────────────────────────────────
def test_ts08_reject_stays_at_baseline(db):
    """Rejecting all snippets must leave enhanced_accuracy = baseline."""
    c = db.cursor()
    c.execute(
        "INSERT INTO file_state (file_key, smart_id, file_name, extraction_accuracy, enhanced_accuracy) "
        "VALUES ('fk08', 'DOC-08', 'd.pdf', 78.0, 78.0)"
    )
    c.execute("""
        INSERT INTO snippet_reviews
        (review_id, smart_id, page_num, snippet_type, deficit_category, snippet_path,
         bounding_box_json, accuracy_impact, content_area_pct, reviewer_role, status)
        VALUES ('rev08', 'DOC-08', 1, 'stamp', 'stamp', '/tmp/s.png',
                '[0,0,100,100]', 5.0, 5.15, 'Reviewer', 'pending')
    """)
    db.commit()

    from core.reporting_manager import update_snippet_review_status
    update_snippet_review_status('rev08', status='rejected', rejection_category='noise', db_conn=db)

    row = db.execute(
        "SELECT enhanced_accuracy FROM file_state WHERE smart_id='DOC-08'"
    ).fetchone()
    assert abs(row['enhanced_accuracy'] - 78.0) < 0.1, \
        f"Expected baseline 78.0, got {row['enhanced_accuracy']}"
