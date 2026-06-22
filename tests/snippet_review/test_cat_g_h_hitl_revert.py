"""
Category G — HITL Review Flow (TS-46 to TS-52)
Category H — Revert & Undo (TS-53 to TS-57)

Tests Human-in-the-Loop review and revert operations.
"""
import json
import threading
import pytest
import sys
sys.path.insert(0, "c:/Users/DELL/Music/DocumentSearch/src")


# ═══════════════════════════════════════════════════════════════════════════════
# CATEGORY G — HITL Review Flow
# ═══════════════════════════════════════════════════════════════════════════════

def _seed_snippet(c, rev_id, smart_id, snip_type='stamp', deficit='stamp',
                  status='pending', accuracy_impact=3.0, content_pct=3.09):
    c.execute("""
        INSERT INTO snippet_reviews
        (review_id, smart_id, page_num, snippet_type, deficit_category, snippet_path,
         bounding_box_json, accuracy_impact, content_area_pct, reviewer_role, status)
        VALUES (?, ?, 1, ?, ?, '/tmp/s.png', '[0,0,200,200]', ?, ?, 'Reviewer', ?)
    """, (rev_id, smart_id, snip_type, deficit, accuracy_impact, content_pct, status))


# ─── TS-46 ──────────────────────────────────────────────────────────────────
def test_ts46_accept_updates_status_and_accuracy_atomically(db):
    """D-01, D-08: Accept must update both status and enhanced_accuracy."""
    c = db.cursor()
    c.execute(
        "INSERT INTO file_state (file_key, smart_id, file_name, extraction_accuracy, enhanced_accuracy) "
        "VALUES ('fk46', 'DOC-46', 'd.pdf', 80.0, 80.0)"
    )
    c.execute("""
        INSERT INTO page_segmentation_breakdown
        (smart_id, page_num, clean_text_pct, faded_text_pct, whitespace_pct,
         content_area_pct, baseline_accuracy, analyzed_at)
        VALUES ('DOC-46', 1, 80.0, 10.0, 0.0, 100.0, 80.0, '2026-01-01T00:00:00')
    """)
    c.execute("""
        INSERT INTO snippet_reviews
        (review_id, smart_id, page_num, snippet_type, deficit_category, snippet_path,
         bounding_box_json, accuracy_impact, content_area_pct, reviewer_role, status)
        VALUES ('rev46', 'DOC-46', 1, 'text_anomaly', 'faded_text', '/tmp/f.png',
                '[0,300,1000,500]', 10.0, 10.0, 'Faded Text Specialist', 'pending')
    """)
    db.commit()

    from core.reporting_manager import update_snippet_review_status
    update_snippet_review_status(
        'rev46', status='accepted', reviewed_by='tester',
        transcription_text='Invoice Date: March 2026', db_conn=db
    )

    snip = db.execute(
        "SELECT status FROM snippet_reviews WHERE review_id='rev46'"
    ).fetchone()
    fs = db.execute(
        "SELECT enhanced_accuracy FROM file_state WHERE smart_id='DOC-46'"
    ).fetchone()

    assert snip['status'] == 'accepted', "Status not updated to accepted"
    assert fs['enhanced_accuracy'] > 80.0, "Enhanced accuracy not increased after accept"


# ─── TS-47 ──────────────────────────────────────────────────────────────────
def test_ts47_reject_stores_rejection_category(db):
    """D-15: Rejecting a snippet must store a structured rejection_category."""
    c = db.cursor()
    _seed_snippet(c, 'rev47', 'DOC-47', snip_type='logo', deficit='logo')
    db.commit()

    from core.reporting_manager import update_snippet_review_status
    update_snippet_review_status(
        'rev47', status='rejected', rejection_category='noise', db_conn=db
    )

    row = db.execute(
        "SELECT rejection_category FROM snippet_reviews WHERE review_id='rev47'"
    ).fetchone()
    assert row['rejection_category'] == 'noise', \
        f"Expected 'noise', got '{row['rejection_category']}'"


# ─── TS-48 ──────────────────────────────────────────────────────────────────
def test_ts48_empty_transcription_blocked_for_faded_text():
    """D-14: Accepting a faded_text snippet with no transcription must raise ValueError."""
    from core.reporting_manager import validate_accept_payload
    with pytest.raises(ValueError, match="transcription"):
        validate_accept_payload(
            deficit_category='faded_text',
            transcription_text='',
            reason='test'
        )


# ─── TS-49 ──────────────────────────────────────────────────────────────────
def test_ts49_sql_injection_in_transcription_is_safe(db):
    """Security: Malicious transcription must be stored as a literal string."""
    c = db.cursor()
    _seed_snippet(c, 'rev49', 'DOC-49', snip_type='text_anomaly', deficit='faded_text',
                  accuracy_impact=1.0, content_pct=1.03)
    db.commit()

    malicious = "'; DROP TABLE snippet_reviews; --"
    from core.reporting_manager import update_snippet_review_status
    update_snippet_review_status(
        'rev49', status='accepted',
        transcription_text=malicious, db_conn=db
    )

    # Table must still exist
    rows = db.execute("SELECT COUNT(*) FROM snippet_reviews").fetchone()[0]
    assert rows >= 1, "snippet_reviews table was dropped (SQL injection)"

    row = db.execute(
        "SELECT transcription_text FROM snippet_reviews WHERE review_id='rev49'"
    ).fetchone()
    assert row['transcription_text'] == malicious, "Transcription not stored literally"


# ─── TS-50 ──────────────────────────────────────────────────────────────────
def test_ts50_concurrent_accept_idempotent(db):
    """D-12: Two threads accepting the same review_id must result in exactly 'accepted'."""
    c = db.cursor()
    _seed_snippet(c, 'rev50', 'DOC-50')
    db.commit()

    errors = []
    from core.reporting_manager import update_snippet_review_status

    def accept():
        try:
            update_snippet_review_status('rev50', status='accepted', db_conn=db)
        except Exception as e:
            errors.append(str(e))

    t1 = threading.Thread(target=accept)
    t2 = threading.Thread(target=accept)
    t1.start(); t2.start()
    t1.join(); t2.join()

    rows = db.execute(
        "SELECT status FROM snippet_reviews WHERE review_id='rev50'"
    ).fetchall()
    assert len(rows) == 1, "Duplicate rows created"
    assert rows[0]['status'] == 'accepted', "Final status is not accepted"


# ─── TS-51 ──────────────────────────────────────────────────────────────────
def test_ts51_activity_log_written_on_reject(db):
    """D-15: Every reject must write a corresponding review_activity_log entry."""
    c = db.cursor()
    _seed_snippet(c, 'rev51', 'DOC-51', snip_type='logo', deficit='logo',
                  accuracy_impact=4.0, content_pct=4.12)
    db.commit()

    from core.reporting_manager import update_snippet_review_status
    update_snippet_review_status(
        'rev51', status='rejected', rejection_category='duplicate', db_conn=db
    )

    logs = db.execute(
        "SELECT action FROM review_activity_log WHERE review_id='rev51'"
    ).fetchall()
    assert len(logs) >= 1, "No activity log entry written"
    actions = [l['action'] for l in logs]
    assert any('reject' in a.lower() for a in actions), \
        f"No reject action found in log: {actions}"


# ─── TS-52 ──────────────────────────────────────────────────────────────────
def test_ts52_missing_snippet_file_graceful(db):
    """D-11: Snippet with missing PNG must not crash the system."""
    c = db.cursor()
    _seed_snippet(c, 'rev52', 'DOC-52', snip_type='stamp', deficit='stamp')
    db.execute(
        "UPDATE snippet_reviews SET snippet_path='/nonexistent/path/s.png' WHERE review_id='rev52'"
    )
    db.commit()

    from ui.review_tab import _resolve_snippet_path
    result = _resolve_snippet_path("/nonexistent/path/s.png", "/some/working/root")
    # Must return a path or None — never raise
    assert result is None or isinstance(result, str), \
        f"Expected str or None, got {type(result)}"


# ═══════════════════════════════════════════════════════════════════════════════
# CATEGORY H — Revert & Undo
# ═══════════════════════════════════════════════════════════════════════════════

# ─── TS-53 ──────────────────────────────────────────────────────────────────
def test_ts53_revert_accepted_snippet_returns_to_pending(db):
    """D-08: Reverting an accepted snippet must reset status to 'pending'."""
    c = db.cursor()
    c.execute(
        "INSERT INTO file_state (file_key, smart_id, file_name, extraction_accuracy, enhanced_accuracy, approval_status) "
        "VALUES ('fk53', 'DOC-53', 'd.pdf', 80.0, 92.0, 'Approved')"
    )
    c.execute("""
        INSERT INTO page_segmentation_breakdown
        (smart_id, page_num, clean_text_pct, faded_text_pct, whitespace_pct,
         content_area_pct, baseline_accuracy, analyzed_at)
        VALUES ('DOC-53', 1, 80.0, 12.0, 0.0, 100.0, 80.0, '2026-01-01T00:00:00')
    """)
    c.execute("""
        INSERT INTO snippet_reviews
        (review_id, smart_id, page_num, snippet_type, deficit_category, snippet_path,
         bounding_box_json, accuracy_impact, content_area_pct, reviewer_role,
         status, reviewed_by, review_reason)
        VALUES ('rev53', 'DOC-53', 1, 'text_anomaly', 'faded_text', '/tmp/f.png',
                '[0,300,1000,500]', 12.0, 12.0, 'Faded Text Specialist',
                'accepted', 'tester', 'test')
    """)
    db.commit()

    from core.reporting_manager import revert_snippet_review
    revert_snippet_review('rev53', reverted_by='admin', db_conn=db)

    snip = db.execute(
        "SELECT status FROM snippet_reviews WHERE review_id='rev53'"
    ).fetchone()
    fs = db.execute(
        "SELECT enhanced_accuracy FROM file_state WHERE smart_id='DOC-53'"
    ).fetchone()

    assert snip['status'] == 'pending', f"Status should be 'pending', got '{snip['status']}'"
    assert fs['enhanced_accuracy'] <= 80.0 + 1.0, \
        f"After revert, enhanced_accuracy should be near baseline, got {fs['enhanced_accuracy']}"


# ─── TS-54 ──────────────────────────────────────────────────────────────────
def test_ts54_revert_creates_activity_log_entry(db):
    """D-08: Revert must append a revert_accept log entry."""
    c = db.cursor()
    _seed_snippet(c, 'rev54', 'DOC-54', status='accepted')
    c.execute(
        "INSERT INTO review_activity_log (review_id, smart_id, action, timestamp) "
        "VALUES ('rev54', 'DOC-54', 'accepted', '2026-01-01T00:00:00')"
    )
    db.commit()

    from core.reporting_manager import revert_snippet_review
    revert_snippet_review('rev54', reverted_by='admin', db_conn=db)

    logs = db.execute(
        "SELECT action, is_cancelled FROM review_activity_log WHERE review_id='rev54' ORDER BY id"
    ).fetchall()
    actions = [l['action'] for l in logs]
    has_revert = any('revert' in a.lower() for a in actions)
    assert has_revert, f"No revert action found in log: {actions}"


# ─── TS-55 ──────────────────────────────────────────────────────────────────
def test_ts55_revert_without_png_does_not_crash(db):
    """D-08: Revert must work even if the crop PNG was deleted."""
    c = db.cursor()
    _seed_snippet(c, 'rev55', 'DOC-55', snip_type='logo', deficit='logo', status='accepted')
    db.execute(
        "UPDATE snippet_reviews SET snippet_path='/deleted/path.png' WHERE review_id='rev55'"
    )
    db.commit()

    from core.reporting_manager import revert_snippet_review
    revert_snippet_review('rev55', reverted_by='admin', db_conn=db)  # Must not raise

    row = db.execute(
        "SELECT status FROM snippet_reviews WHERE review_id='rev55'"
    ).fetchone()
    assert row['status'] == 'pending', f"Status should be 'pending', got '{row['status']}'"


# ─── TS-56 ──────────────────────────────────────────────────────────────────
def test_ts56_revert_rejected_snippet(db):
    """D-08: Reverting a rejected snippet must return it to 'pending'."""
    c = db.cursor()
    _seed_snippet(c, 'rev56', 'DOC-56', status='rejected')
    db.commit()

    from core.reporting_manager import revert_snippet_review
    revert_snippet_review('rev56', reverted_by='admin', db_conn=db)

    row = db.execute(
        "SELECT status FROM snippet_reviews WHERE review_id='rev56'"
    ).fetchone()
    assert row['status'] == 'pending', f"Status should be 'pending', got '{row['status']}'"


# ─── TS-57 ──────────────────────────────────────────────────────────────────
def test_ts57_revert_already_pending_is_noop(db):
    """D-08: Reverting a snippet that's already pending must be safe."""
    c = db.cursor()
    _seed_snippet(c, 'rev57', 'DOC-57', snip_type='logo', status='pending')
    db.commit()

    from core.reporting_manager import revert_snippet_review
    # Must not raise; already-pending revert is a no-op
    result = revert_snippet_review('rev57', reverted_by='admin', db_conn=db)

    row = db.execute(
        "SELECT status FROM snippet_reviews WHERE review_id='rev57'"
    ).fetchone()
    assert row['status'] == 'pending', "Status must remain 'pending' after no-op revert"
