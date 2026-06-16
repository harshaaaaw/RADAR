#!/usr/bin/env python3
"""
Seed realistic visual review crop elements into SQLite audit database and disk
to enable comprehensive side-by-side testing of the Human-in-the-Loop audit portal.
"""
import json
import os
import sqlite3
from pathlib import Path
from PIL import Image, ImageDraw

def main():
    print("==================================================")
    print("Seeding Visual Review Audit Portal & Crops")
    print("==================================================")
    
    # 1. Setup paths
    base_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    working_root = base_dir / "runtime"
    db_path = working_root / "audit" / "audit.db"
    review_dir = working_root / "data" / "review_snippets"
    
    review_dir.mkdir(parents=True, exist_ok=True)
    
    if not db_path.exists():
        # Ensure audit directory exists and make dummy DB
        (working_root / "audit").mkdir(parents=True, exist_ok=True)
        
    print(f"Audit database: {db_path}")
    print(f"Snippets folder: {review_dir}")
    
    # 2. Connect to database
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    
    # Ensure tables exist
    conn.execute("""
        CREATE TABLE IF NOT EXISTS file_state (
            file_key TEXT PRIMARY KEY,
            smart_id TEXT UNIQUE,
            file_name TEXT,
            current_status TEXT,
            processed_on TEXT,
            file_type TEXT,
            file_size INTEGER,
            file_path TEXT,
            extraction_accuracy REAL,
            enhanced_accuracy REAL,
            approval_status TEXT,
            pipeline_type TEXT,
            text_area_pct REAL,
            non_text_area_pct REAL,
            preprocessing_gain_pct REAL,
            accuracy_loss_json TEXT,
            page_metrics_json TEXT,
            accuracy_tier TEXT
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS snippet_reviews (
            review_id TEXT PRIMARY KEY,
            smart_id TEXT,
            page_num INTEGER,
            snippet_type TEXT,
            snippet_path TEXT,
            bounding_box_json TEXT,
            accuracy_impact REAL,
            reviewer_role TEXT,
            status TEXT DEFAULT 'pending',
            feature_vector_path TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    
    # 3. Clean any existing mock elements to avoid key conflicts
    mock_ids = ["VND-20260527-GE01", "BRD-20260527-GE02", "MKT-20260527-GE03"]
    for mid in mock_ids:
        conn.execute("DELETE FROM file_state WHERE smart_id = ?", (mid,))
        conn.execute("DELETE FROM snippet_reviews WHERE smart_id = ?", (mid,))
    conn.commit()
    
    # 4. Generate high-quality visual crops using PIL
    print("\nGenerating visual crops on disk...")
    
    # Colors
    bg_color = (255, 255, 255)
    sig_color = (13, 85, 204)      # Classic blue pen ink
    stamp_color = (204, 25, 25)    # Red rubber stamp ink
    logo_color = (124, 58, 237)    # Modern violet logo color
    
    # A. Crop 1: Signature 1
    sig1_path = review_dir / "VND-20260527-GE01_p1_sig.png"
    img_sig1 = Image.new("RGB", (250, 120), bg_color)
    draw = ImageDraw.Draw(img_sig1)
    # Draw handwritten cursive loop lines
    draw.arc([20, 20, 200, 100], start=30, end=330, fill=sig_color, width=3)
    draw.line([30, 70, 70, 40], fill=sig_color, width=3)
    draw.line([70, 40, 100, 80], fill=sig_color, width=3)
    draw.line([100, 80, 140, 30], fill=sig_color, width=3)
    draw.line([140, 30, 180, 90], fill=sig_color, width=3)
    draw.line([160, 75, 230, 65], fill=sig_color, width=2) # dash
    img_sig1.save(str(sig1_path))
    print(f"  Saved Signature crop: {sig1_path.name}")
    
    # B. Crop 2: Signature 2
    sig2_path = review_dir / "BRD-20260527-GE02_p3_sig.png"
    img_sig2 = Image.new("RGB", (250, 120), bg_color)
    draw = ImageDraw.Draw(img_sig2)
    draw.arc([15, 30, 180, 90], start=0, end=360, fill=sig_color, width=3)
    draw.line([40, 65, 90, 20], fill=sig_color, width=3)
    draw.line([90, 20, 120, 85], fill=sig_color, width=3)
    draw.line([120, 85, 240, 45], fill=sig_color, width=2)
    img_sig2.save(str(sig2_path))
    print(f"  Saved Signature crop: {sig2_path.name}")
    
    # C. Crop 3: Stamp 1
    stamp1_path = review_dir / "VND-20260527-GE01_p2_stamp.png"
    img_stamp1 = Image.new("RGB", (160, 160), bg_color)
    draw = ImageDraw.Draw(img_stamp1)
    # Circle
    draw.ellipse([15, 15, 145, 145], outline=stamp_color, width=4)
    draw.ellipse([22, 22, 138, 138], outline=stamp_color, width=1)
    # Text fallback lines (since default font doesn't scale easily without external files)
    draw.line([40, 50, 120, 50], fill=stamp_color, width=2)
    draw.line([50, 80, 110, 80], fill=stamp_color, width=3)
    draw.line([40, 110, 120, 110], fill=stamp_color, width=2)
    img_stamp1.save(str(stamp1_path))
    print(f"  Saved Stamp crop: {stamp1_path.name}")
    
    # D. Crop 4: Stamp 2
    stamp2_path = review_dir / "BRD-20260527-GE02_p1_stamp.png"
    img_stamp2 = Image.new("RGB", (160, 160), bg_color)
    draw = ImageDraw.Draw(img_stamp2)
    draw.rectangle([15, 30, 145, 130], outline=stamp_color, width=4)
    draw.line([30, 60, 130, 60], fill=stamp_color, width=2)
    draw.line([40, 80, 120, 80], fill=stamp_color, width=3)
    draw.line([30, 100, 130, 100], fill=stamp_color, width=2)
    img_stamp2.save(str(stamp2_path))
    print(f"  Saved Stamp crop: {stamp2_path.name}")

    # E. Crop 5: Stamp 3
    stamp3_path = review_dir / "MKT-20260527-GE03_p1_stamp.png"
    img_stamp3 = Image.new("RGB", (160, 160), bg_color)
    draw = ImageDraw.Draw(img_stamp3)
    draw.ellipse([15, 15, 145, 145], outline=stamp_color, width=4)
    draw.line([35, 65, 125, 65], fill=stamp_color, width=3)
    draw.line([45, 95, 115, 95], fill=stamp_color, width=2)
    img_stamp3.save(str(stamp3_path))
    print(f"  Saved Stamp crop: {stamp3_path.name}")
    
    # F. Crop 6: Logo 1
    logo1_path = review_dir / "VND-20260527-GE01_p1_logo.png"
    img_logo1 = Image.new("RGB", (150, 150), bg_color)
    draw = ImageDraw.Draw(img_logo1)
    # Shape
    draw.polygon([(75, 20), (130, 110), (20, 110)], fill=logo_color)
    draw.ellipse([50, 55, 100, 105], fill=bg_color)
    draw.rectangle([40, 120, 110, 135], fill=logo_color)
    img_logo1.save(str(logo1_path))
    print(f"  Saved Logo crop: {logo1_path.name}")
    
    # G. Crop 7: Logo 2
    logo2_path = review_dir / "MKT-20260527-GE03_p1_logo.png"
    img_logo2 = Image.new("RGB", (150, 150), bg_color)
    draw = ImageDraw.Draw(img_logo2)
    draw.rectangle([30, 20, 120, 110], fill=logo_color, width=0)
    draw.ellipse([45, 35, 105, 95], fill=bg_color)
    draw.rectangle([45, 120, 105, 135], fill=logo_color)
    img_logo2.save(str(logo2_path))
    print(f"  Saved Logo crop: {logo2_path.name}")

    # 5. Insert mock file states into SQLite
    print("\nInserting mock document states...")
    
    # Doc 1
    conn.execute("""
        INSERT INTO file_state (
            file_key, smart_id, file_name, current_status, processed_on,
            file_type, file_size, file_path, extraction_accuracy, enhanced_accuracy,
            approval_status, pipeline_type, text_area_pct, non_text_area_pct, preprocessing_gain_pct,
            accuracy_loss_json, page_metrics_json, accuracy_tier
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "mock_file_key_VND01", "VND-20260527-GE01", "Vendor_Agreement_GE_Capital_Restricted.pdf", 
        "completed", "2026-05-27T16:50:00Z", "pdf", 125000, 
        r"C:\Users\DELL\Downloads\DocumentSearch\test_data\Vendor_Agreement_GE_Capital_Restricted.pdf",
        70.0, 70.0, "Pending Review", "ocr", 65.0, 35.0, 5.0,
        json.dumps({"signatures_pct": 15.0, "stamps_seals_pct": 10.0, "logos_images_pct": 5.0}),
        "[]", "tier3"
    ))
    
    # Doc 2
    conn.execute("""
        INSERT INTO file_state (
            file_key, smart_id, file_name, current_status, processed_on,
            file_type, file_size, file_path, extraction_accuracy, enhanced_accuracy,
            approval_status, pipeline_type, text_area_pct, non_text_area_pct, preprocessing_gain_pct,
            accuracy_loss_json, page_metrics_json, accuracy_tier
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "mock_file_key_BRD02", "BRD-20260527-GE02", "Board_Minutes_GECC_HQ_Confidential.pdf", 
        "completed", "2026-05-27T16:52:00Z", "pdf", 89000, 
        r"C:\Users\DELL\Downloads\DocumentSearch\test_data\Board_Minutes_GECC_HQ_Confidential.pdf",
        75.0, 75.0, "Pending Review", "ocr", 72.0, 28.0, 4.0,
        json.dumps({"signatures_pct": 15.0, "stamps_seals_pct": 10.0}),
        "[]", "tier3"
    ))
    
    # Doc 3
    conn.execute("""
        INSERT INTO file_state (
            file_key, smart_id, file_name, current_status, processed_on,
            file_type, file_size, file_path, extraction_accuracy, enhanced_accuracy,
            approval_status, pipeline_type, text_area_pct, non_text_area_pct, preprocessing_gain_pct,
            accuracy_loss_json, page_metrics_json, accuracy_tier
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "mock_file_key_MKT03", "MKT-20260527-GE03", "Marketing_Logo_GECC_Public.pdf", 
        "completed", "2026-05-27T16:54:00Z", "pdf", 210000, 
        r"C:\Users\DELL\Downloads\DocumentSearch\test_data\Marketing_Logo_GECC_Public.pdf",
        85.0, 85.0, "Pending Review", "ocr", 82.0, 18.0, 6.0,
        json.dumps({"stamps_seals_pct": 10.0, "logos_images_pct": 5.0}),
        "[]", "tier3"
    ))
    conn.commit()
    print("  Successfully inserted 3 pending documents")

    # 6. Insert pending visual review elements
    print("\nInserting pending reviews in database...")
    
    # Element 1: Doc 1 Signature (Impact: 15%)
    conn.execute("""
        INSERT INTO snippet_reviews (
            review_id, smart_id, page_num, snippet_type, snippet_path,
            bounding_box_json, accuracy_impact, reviewer_role, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "VND-20260527-GE01_p1_sig", "VND-20260527-GE01", 1, "signature", str(sig1_path),
        json.dumps([100, 200, 300, 400]), 15.0, "Contract Auditor", "pending"
    ))
    
    # Element 2: Doc 1 Stamp (Impact: 10%)
    conn.execute("""
        INSERT INTO snippet_reviews (
            review_id, smart_id, page_num, snippet_type, snippet_path,
            bounding_box_json, accuracy_impact, reviewer_role, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "VND-20260527-GE01_p2_stamp", "VND-20260527-GE01", 2, "stamp", str(stamp1_path),
        json.dumps([150, 250, 350, 450]), 10.0, "Operations Manager", "pending"
    ))
    
    # Element 3: Doc 1 Logo (Impact: 5%)
    conn.execute("""
        INSERT INTO snippet_reviews (
            review_id, smart_id, page_num, snippet_type, snippet_path,
            bounding_box_json, accuracy_impact, reviewer_role, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "VND-20260527-GE01_p1_logo", "VND-20260527-GE01", 1, "logo", str(logo1_path),
        json.dumps([50, 50, 150, 150]), 5.0, "Marketing Reviewer", "pending"
    ))
    
    # Element 4: Doc 2 Signature (Impact: 15%)
    conn.execute("""
        INSERT INTO snippet_reviews (
            review_id, smart_id, page_num, snippet_type, snippet_path,
            bounding_box_json, accuracy_impact, reviewer_role, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "BRD-20260527-GE02_p3_sig", "BRD-20260527-GE02", 3, "signature", str(sig2_path),
        json.dumps([120, 220, 320, 420]), 15.0, "Contract Auditor", "pending"
    ))
    
    # Element 5: Doc 2 Stamp (Impact: 10%)
    conn.execute("""
        INSERT INTO snippet_reviews (
            review_id, smart_id, page_num, snippet_type, snippet_path,
            bounding_box_json, accuracy_impact, reviewer_role, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "BRD-20260527-GE02_p1_stamp", "BRD-20260527-GE02", 1, "stamp", str(stamp2_path),
        json.dumps([180, 280, 380, 480]), 10.0, "Operations Manager", "pending"
    ))
    
    # Element 6: Doc 3 Stamp (Impact: 10%)
    conn.execute("""
        INSERT INTO snippet_reviews (
            review_id, smart_id, page_num, snippet_type, snippet_path,
            bounding_box_json, accuracy_impact, reviewer_role, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "MKT-20260527-GE03_p1_stamp", "MKT-20260527-GE03", 1, "stamp", str(stamp3_path),
        json.dumps([110, 210, 310, 410]), 10.0, "Operations Manager", "pending"
    ))
    
    # Element 7: Doc 3 Logo (Impact: 5%)
    conn.execute("""
        INSERT INTO snippet_reviews (
            review_id, smart_id, page_num, snippet_type, snippet_path,
            bounding_box_json, accuracy_impact, reviewer_role, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "MKT-20260527-GE03_p1_logo", "MKT-20260527-GE03", 1, "logo", str(logo2_path),
        json.dumps([40, 40, 140, 140]), 5.0, "Marketing Reviewer", "pending"
    ))
    
    conn.commit()
    conn.close()
    
    print("  Successfully inserted 7 pending visual reviews")
    print("==================================================")
    print("Seeding Complete! Audit portal has active reviews.")
    print("==================================================")
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
