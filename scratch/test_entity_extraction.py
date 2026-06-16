import sys
import os
import sqlite3
import json

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from core.config_manager import get_config
from tagging.tagging_engine import TaggingEngine, TaggingRequest

config = get_config()
audit_db = os.path.join(config.paths.working_root, "audit", "audit.db")

conn = sqlite3.connect(audit_db)
conn.row_factory = sqlite3.Row

# Get 5 sample documents with actual content
rows = conn.execute(
    "SELECT file_name, file_path, main_content, ocr_content, embedded_content, category, department "
    "FROM file_state WHERE current_status IN ('completed', 'tag_completed') LIMIT 5"
).fetchall()

engine = TaggingEngine()

for idx, r in enumerate(rows, start=1):
    print(f"\nDocument #{idx}: {r['file_name']}")
    print("-" * 50)
    main_c = r['main_content'] or ""
    ocr_c = r['ocr_content'] or ""
    emb_c = r['embedded_content'] or ""
    
    print(f"Content Lengths: Main={len(main_c)}, OCR={len(ocr_c)}, Embedded={len(emb_c)}")
    
    # Run tag
    req = TaggingRequest(
        file_path=r['file_path'],
        file_name=r['file_name'],
        main_content=main_c,
        ocr_content=ocr_c,
        embedded_content=emb_c
    )
    
    res = engine.tag(req)
    print(f"Category: {res.category} (BU: {res.business_unit_name}, SubBU: {res.sub_business_unit_name}, Code: {res.record_type_code})")
    print(f"Country: {res.iso_country_code}")
    print(f"Confidentiality: {res.confidentiality}")
    print(f"Key Names: {res.key_names}")
    print(f"Amount Found: {res.amount_found}")
    print(f"Important Dates: {res.important_dates}")
    print(f"Locations Mentioned: {res.location_mentioned}")
    print(f"Dynamic Subtags: {res.dynamic_subtags}")

conn.close()
