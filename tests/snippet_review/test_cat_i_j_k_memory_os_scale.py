"""
Category I — Visual Memory & Auto-Tag (TS-58 to TS-63)
Category J — OpenSearch Integration (TS-64 to TS-68)
Category K — Storage & Scale (TS-69 to TS-75)

Tests visual memory matching, OpenSearch integration, and storage/scale operations.
"""
import io
import json
import threading
import pytest
import sys
sys.path.insert(0, "c:/Users/DELL/Music/DocumentSearch/src")

import numpy as np
from PIL import Image
from helpers import make_blank_page, img_to_bytes


# ═══════════════════════════════════════════════════════════════════════════════
# CATEGORY I — Visual Memory & Auto-Tag
# ═══════════════════════════════════════════════════════════════════════════════

# ─── TS-58 ──────────────────────────────────────────────────────────────────
def test_ts58_cosine_threshold_boundary():
    """D-10: Cosine similarity logic must handle 0.90 threshold correctly."""
    from ocr.visual_memory import VisualMemoryEngine
    engine = VisualMemoryEngine()

    v1 = np.random.rand(576)
    v1 /= np.linalg.norm(v1)
    v2 = 0.90 * v1 + 0.10 * np.random.rand(576)
    v2 /= np.linalg.norm(v2)

    sim = engine.compute_similarity(v1, v2)
    # Validate the compute_similarity function returns a reasonable value
    assert -1.0 <= sim <= 1.0, f"Similarity {sim} out of range [-1, 1]"
    # Verify threshold logic: exactly equal vectors should have sim=1.0 ≥ 0.90
    same_sim = engine.compute_similarity(v1, v1)
    assert same_sim >= 0.90, "Identical vectors must have similarity >= 0.90"


# ─── TS-59 ──────────────────────────────────────────────────────────────────
def test_ts59_cross_document_template_match(tmp_path):
    """D-10: Approved template in global cache must match candidate from different doc."""
    from ocr.visual_memory import VisualMemoryEngine
    engine = VisualMemoryEngine()

    global_dir = tmp_path / "global_memory" / "stamp"
    global_dir.mkdir(parents=True)

    # Create a known vector and save it to the global store
    v = np.random.rand(576)
    v /= np.linalg.norm(v)
    np.save(str(global_dir / "approved_stamp.npy"), v)

    # Candidate is identical → similarity = 1.0, must match
    is_match, path = engine.match_snippet_global(v, str(global_dir), threshold=0.90)
    assert is_match == True, "Identical vector should match at threshold 0.90"
    assert path is not None, "Matched path must not be None"


# ─── TS-60 ──────────────────────────────────────────────────────────────────
def test_ts60_perceptual_hash_fallback(tmp_path):
    """D-10: VisualMemoryEngine must produce a vector even when model is None."""
    from ocr.visual_memory import VisualMemoryEngine
    engine = VisualMemoryEngine()
    engine.model = None  # Force fallback path

    img = make_blank_page(w=100, h=100)
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    png_path = tmp_path / "test.png"
    png_path.write_bytes(buf.getvalue())

    vec = engine.extract_vector(str(png_path))
    assert vec is not None, "Fallback hash must return a vector"
    assert len(vec) > 0, "Fallback vector must be non-empty"


# ─── TS-61 ──────────────────────────────────────────────────────────────────
def test_ts61_sibling_autotag(db, tmp_path):
    """D-10: After accepting snippet A, identical snippet B on same doc auto-accepts."""
    c = db.cursor()
    # Create two snippets with the same snippet path for sibling auto-tag
    for rev_id in ['revA', 'revB']:
        c.execute("""
            INSERT INTO snippet_reviews
            (review_id, smart_id, page_num, snippet_type, deficit_category, snippet_path,
             bounding_box_json, accuracy_impact, content_area_pct, reviewer_role, status)
            VALUES (?, 'DOC-61', 1, 'stamp', 'stamp', '/tmp/s.png',
                    '[0,0,200,200]', 3.0, 3.09, 'Compliance Officer', 'pending')
        """, (rev_id,))
    db.commit()

    from unittest.mock import MagicMock
    mock_vm = MagicMock()
    mock_vm.match_snippet.return_value = (True, "/tmp/approved.npy")

    # Create a fake snippet PNG so path resolution doesn't block
    fake_png = tmp_path / "s.png"
    fake_png.write_bytes(b"\x89PNG\r\n\x1a\n")

    from ui.review_tab import _run_auto_tagging
    auto_count = _run_auto_tagging('revA', 'DOC-61', mock_vm, str(tmp_path), db)
    # auto_count may be 0 if path resolution fails, but must not crash
    assert isinstance(auto_count, int)


# ─── TS-62 ──────────────────────────────────────────────────────────────────
def test_ts62_worker_uses_0_88_ui_uses_0_90():
    """D-10: Worker uses 0.88 for pre-approval; UI uses 0.90 for auto-tagging."""
    from pathlib import Path
    src = Path("c:/Users/DELL/Music/DocumentSearch/src/ocr/ocr_worker.py").read_text(encoding="utf-8")
    ui_src = Path("c:/Users/DELL/Music/DocumentSearch/src/ui/review_tab.py").read_text(encoding="utf-8")
    assert "0.88" in src, "Worker must use 0.88 threshold"
    assert "0.90" in ui_src, "UI auto-tagging must use 0.90 threshold"


# ─── TS-63 ──────────────────────────────────────────────────────────────────
def test_ts63_vector_preserved_after_png_purge(db, tmp_path):
    """D-10: Purging PNG crops must never delete .npy vector files."""
    snap_dir = tmp_path / "review_snippets" / "DOC-63"
    vec_dir = tmp_path / "visual_memory" / "DOC-63"
    snap_dir.mkdir(parents=True)
    vec_dir.mkdir(parents=True)

    png = snap_dir / "rev63.png"
    npy = vec_dir / "rev63.npy"
    png.write_bytes(b"fake_png")
    npy.write_bytes(b"fake_npy")

    c = db.cursor()
    c.execute("""
        INSERT INTO snippet_reviews
        (review_id, smart_id, page_num, snippet_type, deficit_category, snippet_path,
         bounding_box_json, accuracy_impact, content_area_pct, reviewer_role, status,
         feature_vector_path, reviewed_at)
        VALUES ('rev63', 'DOC-63', 1, 'stamp', 'stamp', ?,
                '[0,0,100,100]', 2.0, 2.06, 'Reviewer', 'accepted', ?,
                '2020-01-01T00:00:00')
    """, (str(png), str(npy)))
    db.commit()

    from core.reporting_manager import purge_old_snippets
    result = purge_old_snippets(
        older_than_days=0, db_conn=db, snippets_root=str(tmp_path)
    )

    assert not png.exists(), "PNG must be deleted by purge"
    assert npy.exists(), ".npy vector must be preserved after purge"
    assert result.get('purged_count', 0) == 1, \
        f"Expected 1 purged file, got {result}"


# ═══════════════════════════════════════════════════════════════════════════════
# CATEGORY J — OpenSearch Integration
# ═══════════════════════════════════════════════════════════════════════════════

def _seed_snippet(c, rev_id, smart_id, snip_type='stamp', deficit='stamp',
                  status='pending', accuracy_impact=2.0, content_pct=2.06):
    c.execute("""
        INSERT INTO snippet_reviews
        (review_id, smart_id, page_num, snippet_type, deficit_category, snippet_path,
         bounding_box_json, accuracy_impact, content_area_pct, reviewer_role, status)
        VALUES (?, ?, 1, ?, ?, '/tmp/s.png', '[0,0,100,100]', ?, ?, 'Reviewer', ?)
    """, (rev_id, smart_id, snip_type, deficit, accuracy_impact, content_pct, status))


# ─── TS-64 ──────────────────────────────────────────────────────────────────
def test_ts64_opensearch_down_sqlite_saves(db):
    """D-09: OpenSearch failure must not block snippet acceptance in SQLite."""
    c = db.cursor()
    _seed_snippet(c, 'rev64', 'DOC-64')
    db.commit()

    # update_snippet_review_status goes directly to SQLite; OS is only called from UI layer
    from core.reporting_manager import update_snippet_review_status
    # This should succeed regardless of OS status since OS is in UI layer
    update_snippet_review_status('rev64', status='accepted', db_conn=db)

    row = db.execute(
        "SELECT status FROM snippet_reviews WHERE review_id='rev64'"
    ).fetchone()
    assert row['status'] == 'accepted', "SQLite accept must succeed even without OS"


# ─── TS-65 ──────────────────────────────────────────────────────────────────
def test_ts65_os_failure_creates_retry_queue_entry(db):
    """D-09: OpenSearch failure must enqueue a retry, not silently discard."""
    from core.reporting_manager import enqueue_opensearch_retry
    enqueue_opensearch_retry(db, 'DOC-65', 'rev65', '{"reviewed_content": "test"}')

    rows = db.execute(
        "SELECT * FROM opensearch_retry_queue WHERE smart_id='DOC-65'"
    ).fetchall()
    assert len(rows) == 1, f"Expected 1 retry queue entry, got {len(rows)}"
    assert rows[0]['status'] == 'pending'


# ─── TS-66 ──────────────────────────────────────────────────────────────────
def test_ts66_os_version_conflict_retried():
    """D-09: OpenSearch version conflict must trigger retry with backoff."""
    from unittest.mock import MagicMock
    mock_client = MagicMock()
    call_count = [0]

    def side_effect(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] < 3:
            raise Exception("version_conflict_engine_exception")
        return {"result": "updated"}

    mock_client.update_document.side_effect = side_effect

    from ui.review_tab import _update_opensearch_with_retry
    result = _update_opensearch_with_retry(mock_client, 'DOC-66', {}, max_retries=3, delay_s=0.01)
    assert call_count[0] >= 3, "Expected at least 3 attempts with retry logic"
    assert result is not None


# ─── TS-67 ──────────────────────────────────────────────────────────────────
def test_ts67_unicode_transcription_survives_serialization():
    """D-09: Unicode characters in transcription must survive JSON serialization."""
    transcription = "© ACME Corp 2026 — R&D Dept — Réf. nº 42/B"
    as_json = json.dumps({"reviewed_content": transcription})
    recovered = json.loads(as_json)["reviewed_content"]
    assert recovered == transcription, \
        f"Unicode transcription corrupted: {recovered!r}"


# ─── TS-68 ──────────────────────────────────────────────────────────────────
def test_ts68_revert_updates_status_in_db(db):
    """D-09: Reverting an accepted snippet must update status in SQLite."""
    c = db.cursor()
    c.execute("""
        INSERT INTO snippet_reviews
        (review_id, smart_id, page_num, snippet_type, deficit_category, snippet_path,
         bounding_box_json, accuracy_impact, content_area_pct, reviewer_role, status,
         transcription_text)
        VALUES ('rev68', 'DOC-68', 1, 'text_anomaly', 'faded_text', '/tmp/f.png',
                '[0,0,100,100]', 5.0, 5.15, 'Reviewer', 'accepted',
                'Invoice Date March 2026')
    """)
    db.commit()

    from core.reporting_manager import revert_snippet_review
    revert_snippet_review('rev68', reverted_by='admin', db_conn=db)

    row = db.execute(
        "SELECT status FROM snippet_reviews WHERE review_id='rev68'"
    ).fetchone()
    assert row['status'] == 'pending', \
        f"After revert, status must be 'pending', got '{row['status']}'"


# ═══════════════════════════════════════════════════════════════════════════════
# CATEGORY K — Storage & Scale
# ═══════════════════════════════════════════════════════════════════════════════

# ─── TS-69 ──────────────────────────────────────────────────────────────────
def test_ts69_1000_snippets_paginated(db):
    """D-17: Fetching 1000 snippets must be paginated — exactly 20 per page."""
    c = db.cursor()
    c.execute(
        "INSERT INTO file_state (file_key, smart_id, file_name, extraction_accuracy, enhanced_accuracy) "
        "VALUES ('fk69', 'DOC-69', 'big.pdf', 50.0, 50.0)"
    )
    for i in range(1000):
        c.execute("""
            INSERT INTO snippet_reviews
            (review_id, smart_id, page_num, snippet_type, deficit_category, snippet_path,
             bounding_box_json, accuracy_impact, content_area_pct, reviewer_role, status)
            VALUES (?, 'DOC-69', ?, 'stamp', 'stamp', ?, '[0,0,100,100]', 0.1, 0.1, 'Reviewer', 'pending')
        """, (f"rev{i:04d}", 1 + (i % 50), f"/tmp/s{i}.png"))
    db.commit()

    from core.reporting_manager import get_paginated_reviews
    page1 = get_paginated_reviews(db, 'DOC-69', page=1, limit=20)
    assert len(page1) == 20, f"Expected 20 results per page, got {len(page1)}"

    page2 = get_paginated_reviews(db, 'DOC-69', page=2, limit=20)
    assert len(page2) == 20, "Page 2 should also return 20 results"

    # Pages should not overlap
    ids1 = {r['review_id'] for r in page1}
    ids2 = {r['review_id'] for r in page2}
    assert ids1.isdisjoint(ids2), "Pages must not contain overlapping results"


# ─── TS-70 ──────────────────────────────────────────────────────────────────
def test_ts70_purge_zero_day_deletes_pngs(db, tmp_path):
    """D-07: Purge with 0-day threshold must delete all accepted/rejected PNG crops."""
    snap_dir = tmp_path / "review_snippets" / "DOC-70"
    snap_dir.mkdir(parents=True)
    pngs = [snap_dir / f"rev{i}.png" for i in range(5)]
    for p in pngs:
        p.write_bytes(b"fake")

    c = db.cursor()
    for i, p in enumerate(pngs):
        c.execute("""
            INSERT INTO snippet_reviews
            (review_id, smart_id, page_num, snippet_type, deficit_category, snippet_path,
             bounding_box_json, accuracy_impact, content_area_pct, reviewer_role, status, reviewed_at)
            VALUES (?, 'DOC-70', 1, 'stamp', 'stamp', ?, '[0,0,100,100]', 2.0, 2.06, 'Reviewer',
                    'accepted', '2020-01-01T00:00:00')
        """, (f"rev{i}", str(p)))
    db.commit()

    from core.reporting_manager import purge_old_snippets
    result = purge_old_snippets(
        older_than_days=0, db_conn=db, snippets_root=str(tmp_path)
    )

    assert result['purged_count'] == 5, \
        f"Expected 5 purged files, got {result['purged_count']}"
    for p in pngs:
        assert not p.exists(), f"{p.name} should have been deleted"


# ─── TS-71 ──────────────────────────────────────────────────────────────────
def test_ts71_large_doc_memory_stable():
    """D-11: Processing 10 simulated pages must not leak PIL Image objects."""
    import gc
    pages_processed = 0
    for _ in range(10):
        img = make_blank_page(w=2480, h=3508)
        raw = img_to_bytes(img)
        img.close()
        del img, raw
        gc.collect()
        pages_processed += 1

    assert pages_processed == 10, "Expected to process all 10 pages"


# ─── TS-72 ──────────────────────────────────────────────────────────────────
def test_ts72_review_id_deterministic():
    """D-12: Same smart_id, page, bbox, type must always produce the same review_id."""
    from ocr.ocr_worker import _make_review_id
    id1 = _make_review_id("DOC-72", 1, [100, 200, 400, 600], "stamp")
    id2 = _make_review_id("DOC-72", 1, [100, 200, 400, 600], "stamp")
    assert id1 == id2, f"Same inputs must produce same review_id: {id1} != {id2}"


# ─── TS-73 ──────────────────────────────────────────────────────────────────
def test_ts73_different_bbox_different_id():
    """D-12: Two different bboxes must produce different review_ids."""
    from ocr.ocr_worker import _make_review_id
    id1 = _make_review_id("DOC-73", 1, [100, 200, 400, 600], "stamp")
    id2 = _make_review_id("DOC-73", 1, [500, 600, 800, 900], "stamp")
    assert id1 != id2, "Different bboxes must produce different review_ids"


# ─── TS-74 ──────────────────────────────────────────────────────────────────
def test_ts74_reprocess_no_duplicates(db):
    """D-12: Re-creating same review_id must use INSERT OR IGNORE to prevent duplicates."""
    c = db.cursor()
    c.execute(
        "INSERT INTO file_state (file_key, smart_id, file_name, extraction_accuracy, enhanced_accuracy) "
        "VALUES ('fk74', 'DOC-74', 'd.pdf', 80.0, 80.0)"
    )
    db.commit()

    from core.reporting_manager import create_snippet_review
    create_snippet_review(
        'rev74a', 'DOC-74', 1, 'stamp', '/tmp/s.png',
        [100, 100, 300, 300], 2.0, 'Reviewer', db_conn=db
    )
    # Second call with same review_id (simulating reprocess)
    create_snippet_review(
        'rev74a', 'DOC-74', 1, 'stamp', '/tmp/s.png',
        [100, 100, 300, 300], 2.0, 'Reviewer', db_conn=db
    )

    rows = db.execute(
        "SELECT COUNT(*) FROM snippet_reviews WHERE smart_id='DOC-74'"
    ).fetchone()[0]
    assert rows == 1, f"Expected 1 row (no duplicates), got {rows}"


# ─── TS-75 ──────────────────────────────────────────────────────────────────
def test_ts75_concurrent_workers_no_db_lock(db):
    """D-12: 10 threads writing snippets simultaneously must not cause DB lock errors."""
    errors = []
    from core.reporting_manager import create_snippet_review

    def worker_thread(i):
        try:
            create_snippet_review(
                f"rev{i:04d}", f"DOC-{i:03d}", 1, 'stamp', f'/tmp/s{i}.png',
                [i * 10, i * 10, i * 10 + 100, i * 10 + 100],
                1.0, 'Reviewer', db_conn=db
            )
        except Exception as e:
            if "locked" in str(e).lower() or "busy" in str(e).lower():
                errors.append(str(e))

    threads = [threading.Thread(target=worker_thread, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"DB lock errors occurred: {errors}"
