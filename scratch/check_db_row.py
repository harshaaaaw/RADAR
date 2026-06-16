import json
import sqlite3
from pathlib import Path
from core.config_manager import get_config
from core.reporting_manager import (
    upsert_file_state,
    update_accuracy_metrics,
    create_snippet_review,
    update_snippet_review_status,
    FileStateRow,
)

def run_debug():
    config = get_config()
    working_root = Path(config.paths.working_root)
    db_file = working_root / "audit" / "audit.db"
    
    file_key = "debug_file_key_999"
    smart_id = "debug_smart_id_999"
    
    print("--- 1. Upserting File State ---")
    upsert_file_state(
        FileStateRow(
            file_key=file_key,
            smart_id=smart_id,
            file_name="debug_contract.pdf",
            current_status="completed",
            processed_on="2026-05-27T12:00:00Z",
            file_type="pdf",
            file_size=5000,
            file_path="C:/debug_contract.pdf",
            pipeline_type="ocr",
        )
    )
    
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT extraction_accuracy, enhanced_accuracy FROM file_state WHERE file_key = ?", (file_key,)).fetchone()
    print(f"After upsert - Extraction: {row['extraction_accuracy']}, Enhanced: {row['enhanced_accuracy']}")
    
    print("\n--- 2. Updating Accuracy Metrics ---")
    update_accuracy_metrics(
        file_key,
        {
            "pipeline_type": "ocr",
            "extraction_accuracy": 70.0,
            "text_area_pct": 80.0,
            "non_text_area_pct": 20.0,
            "raw_char_count": 1000,
            "processed_char_count": 950,
            "preprocessing_gain_pct": 5.0,
            "accuracy_loss_json": json.dumps({"signatures_pct": 15.0, "stamps_seals_pct": 10.0}),
            "page_metrics_json": "[]",
            "accuracy_tier": "tier3",
        }
    )
    
    row = conn.execute("SELECT extraction_accuracy, enhanced_accuracy FROM file_state WHERE file_key = ?", (file_key,)).fetchone()
    print(f"After update_accuracy_metrics - Extraction: {row['extraction_accuracy']}, Enhanced: {row['enhanced_accuracy']}")
    
    print("\n--- 3. Creating Snippet Review ---")
    create_snippet_review(
        review_id="debug_rev_1",
        smart_id=smart_id,
        page_num=1,
        snippet_type="signature",
        snippet_path="C:/crop.png",
        bounding_box=[100, 100, 200, 200],
        accuracy_impact=15.0,
        reviewer_role="Contract Auditor"
    )
    
    print("\n--- 4. Accepting Snippet Review ---")
    update_snippet_review_status("debug_rev_1", status="accepted")
    
    row = conn.execute("SELECT extraction_accuracy, enhanced_accuracy, approval_status FROM file_state WHERE file_key = ?", (file_key,)).fetchone()
    print(f"After acceptance - Extraction: {row['extraction_accuracy']}, Enhanced: {row['enhanced_accuracy']}, Status: {row['approval_status']}")
    
    conn.close()

if __name__ == "__main__":
    run_debug()
