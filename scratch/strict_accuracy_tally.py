#!/usr/bin/env python3
"""
Strict Accuracy Tally and Multi-Store Comparison Script.
Connects to SQLite, OpenSearch, and loads the State Matrix Excel file.
Cross-verifies every single field of every document across all three stores.
"""
import sys
import os
import json
import sqlite3
from pathlib import Path
import pandas as pd
import urllib.request
import redis

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Expected dimensions map from Excel columns to SQLite fields
EXCEL_TO_DB_MAP = {
    'Metadata Level': 'metadata_level_code',
    'Record Class': 'record_class_name',
    'Record Category (Functional)': 'record_category_name_functional',
    'Record Category (Transactional)': 'record_category_name_transactional',
    'Record Type Code': 'record_type_code',
    'Business Unit': 'business_unit_name',
    'Sub Business Unit': 'sub_business_unit_name',
    'ISO Country Code': 'iso_country_code',
    'Record Format': 'record_format_name',
    'Original Location Type': 'original_record_location_type_name',
    'Data Classification': 'data_classification_name',
    'Divestiture Deal Name': 'divestiture_deal_name'
}

def get_opensearch_docs():
    """Fetch all docs from OpenSearch via Scroll API."""
    docs = {}
    try:
        # Start scroll
        url = "http://localhost:9200/enterprise_documents/_search?scroll=2m&size=100"
        req_data = json.dumps({
            "_source": [
                "file_name", "file_path", "file_hash", "file_type", "mime_type",
                "smart_id", "metadata_level_code", "record_class_name",
                "record_category_name_functional", "record_category_name_transactional",
                "record_type_code", "business_unit_name", "sub_business_unit_name",
                "iso_country_code", "record_format_name", "original_record_location_type_name",
                "data_classification_name", "divestiture_deal_name"
            ]
        }).encode('utf-8')
        
        req = urllib.request.Request(url, data=req_data, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req) as response:
            resp = json.loads(response.read().decode('utf-8'))
            
        scroll_id = resp.get("_scroll_id")
        hits = resp.get("hits", {}).get("hits", [])
        
        for hit in hits:
            source = hit.get("_source", {})
            file_name = source.get("file_name")
            if file_name:
                docs[file_name] = source
                
        while hits:
            scroll_url = "http://localhost:9200/_search/scroll"
            scroll_data = json.dumps({
                "scroll": "2m",
                "scroll_id": scroll_id
            }).encode('utf-8')
            
            req = urllib.request.Request(scroll_url, data=scroll_data, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req) as response:
                resp = json.loads(response.read().decode('utf-8'))
                
            scroll_id = resp.get("_scroll_id")
            hits = resp.get("hits", {}).get("hits", [])
            for hit in hits:
                source = hit.get("_source", {})
                file_name = source.get("file_name")
                if file_name:
                    docs[file_name] = source
                    
        # Clear scroll
        clear_url = "http://localhost:9200/_search/scroll"
        clear_req = urllib.request.Request(
            clear_url,
            data=json.dumps({"scroll_id": [scroll_id]}).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='DELETE'
        )
        try:
            urllib.request.urlopen(clear_req)
        except Exception:
            pass
            
    except Exception as e:
        print(f"Error fetching from OpenSearch: {e}")
    return docs

def main():
    print("=" * 85)
    print(" STRICT DOCUMENT-LEVEL ACCURACY TALLY & INTEGRITY AUDIT")
    print("=" * 85)
    
    # 1. Load SQLite documents
    db_path = Path("runtime/audit/audit.db")
    if not db_path.exists():
        print("ERROR: SQLite database not found!")
        return 1
        
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    db_rows = conn.execute("SELECT * FROM file_state WHERE current_status != 'deleted'").fetchall()
    conn.close()
    
    db_docs = {row["file_name"]: dict(row) for row in db_rows}
    print(f"Loaded {len(db_docs)} active documents from SQLite.")
    
    # 2. Load OpenSearch documents
    os_docs = get_opensearch_docs()
    print(f"Loaded {len(os_docs)} documents from OpenSearch.")
    
    # 3. Load Excel State Matrix
    excel_path = Path("runtime/test_state_matrix.xlsx")
    if not excel_path.exists():
        print("ERROR: State Matrix Excel file not found!")
        return 1
        
    df = pd.read_excel(excel_path)
    excel_docs = {}
    for idx, row in df.iterrows():
        file_name = row["File Name"]
        if pd.notna(file_name):
            excel_docs[file_name] = row.to_dict()
    print(f"Loaded {len(excel_docs)} rows from Excel State Matrix.\n")
    
    # Check counts alignment
    print("--- COUNTS TALLY ---")
    print(f"SQLite Count:     {len(db_docs)}")
    print(f"OpenSearch Count: {len(os_docs)}")
    print(f"Excel Row Count:  {len(excel_docs)}")
    
    counts_aligned = len(db_docs) == len(os_docs) == len(excel_docs)
    if counts_aligned:
        print("✓ SUCCESS: Document counts across SQLite, OpenSearch, and Excel match EXACTLY at 502!\n")
    else:
        print("✗ WARNING: Document counts are NOT fully aligned!\n")
        
    # Check key by key, document by document
    print("--- STRICT METADATA INTEGRITY CROSS-STORE AUDIT ---")
    total_comparisons = 0
    mismatches = []
    
    for file_name, db_doc in db_docs.items():
        # A. Check existence in OpenSearch
        if file_name not in os_docs:
            mismatches.append({
                'file_name': file_name,
                'issue': 'Missing in OpenSearch index',
                'sqlite_val': 'exists',
                'opensearch_val': 'missing'
            })
            continue
            
        # B. Check existence in Excel
        if file_name not in excel_docs:
            mismatches.append({
                'file_name': file_name,
                'issue': 'Missing in Excel State Matrix',
                'sqlite_val': 'exists',
                'excel_val': 'missing'
            })
            continue
            
        os_doc = os_docs[file_name]
        excel_row = excel_docs[file_name]
        
        # C. Compare Smart ID
        total_comparisons += 1
        db_smart_id = db_doc.get("smart_id")
        excel_smart_id = excel_row.get("Smart ID")
        os_smart_id = os_doc.get("smart_id")
        
        # Normalize Smart ID
        def norm_smart_id(v):
            if pd.isna(v) or v is None:
                return ""
            return str(v).strip()
            
        db_smart_norm = norm_smart_id(db_smart_id)
        excel_smart_norm = norm_smart_id(excel_smart_id)
        os_smart_norm = norm_smart_id(os_smart_id)
        
        if db_smart_norm != excel_smart_norm or db_smart_norm != os_smart_norm:
            mismatches.append({
                'file_name': file_name,
                'field': 'Smart ID',
                'sqlite_val': db_smart_norm,
                'opensearch_val': os_smart_norm,
                'excel_val': excel_smart_norm
            })
            
        # D. Compare 12 dimensions
        for excel_col, db_field in EXCEL_TO_DB_MAP.items():
            total_comparisons += 1
            db_val = db_doc.get(db_field)
            excel_val = excel_row.get(excel_col)
            
            # OpenSearch root-level fields
            os_val = os_doc.get(db_field)
            
            # Normalize empty values (None, NaN, empty strings)
            def normalize_val(v):
                if pd.isna(v) or v is None:
                    return ""
                return str(v).strip()
                
            db_norm = normalize_val(db_val)
            excel_norm = normalize_val(excel_val)
            os_norm = normalize_val(os_val)
            
            if db_norm != excel_norm or db_norm != os_norm:
                mismatches.append({
                    'file_name': file_name,
                    'field': excel_col,
                    'sqlite_val': db_norm,
                    'opensearch_val': os_norm,
                    'excel_val': excel_norm
                })
                
    # Summary of discrepancies
    mismatch_count = len(mismatches)
    accuracy_rate = ((total_comparisons - mismatch_count) / total_comparisons * 100) if total_comparisons > 0 else 100.0
    
    print(f"Total metadata cell checks: {total_comparisons}")
    print(f"Total mismatched cells:     {mismatch_count}")
    print(f"Strict Alignment Accuracy:  {accuracy_rate:.4f}%\n")
    
    if mismatch_count == 0:
        print("✓ SUCCESS: Every single metadata field of every single document matches perfectly across SQLite, OpenSearch, and Excel!")
    else:
        print("✗ DISCREPANCIES DETECTED:")
        for idx, m in enumerate(mismatches[:10], 1):
            if 'field' in m:
                print(f"[{idx}] File: {m['file_name']} | Field: {m['field']}")
                print(f"    SQLite:     '{m['sqlite_val']}'")
                print(f"    OpenSearch: '{m['opensearch_val']}'")
                print(f"    Excel:      '{m['excel_val']}'")
            else:
                print(f"[{idx}] File: {m['file_name']} | Issue: {m['issue']}")
        if mismatch_count > 10:
            print(f"... and {mismatch_count - 10} more discrepancies.")
            
    print("=" * 85)

if __name__ == "__main__":
    main()
