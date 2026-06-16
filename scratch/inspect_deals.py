import sqlite3
import re
from pathlib import Path
import os
import sys

# Insert src directory to path
SYS_PATH = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SYS_PATH))

from tagging.metadata_manager import get_metadata_manager

def main():
    db_path = Path(__file__).resolve().parent.parent / "runtime" / "audit" / "audit.db"
    if not db_path.exists():
        print(f"DB not found at {db_path}")
        return

    mgr = get_metadata_manager()
    snap = mgr.ensure_loaded()
    if not snap or not snap.sheet3_allowed_values or 'divestiture_deal_name' not in snap.sheet3_allowed_values:
        print("Failed to load deal names from Sheet 3 registry")
        return
        
    deals = sorted(list(snap.sheet3_allowed_values['divestiture_deal_name']))
    print(f"Loaded {len(deals)} divestiture deal names.")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT file_key, file_name, file_path, category, department FROM file_state WHERE current_status != 'deleted'")
    rows = cursor.fetchall()
    print(f"Total active rows in file_state: {len(rows)}")

    # Let's also check if we can access the original OCR/main content from SQLite or if it's only in OpenSearch
    # Wait, SQLite has a file_state table, but does it store main_content/ocr_content? Let's check table columns.
    cursor.execute("PRAGMA table_info(file_state)")
    columns = [col[1] for col in cursor.fetchall()]
    print(f"Columns in file_state: {columns}")

    # Let's fetch from OpenSearch to scan the full text of all documents for these deal names!
    try:
        from indexing.opensearch_client import OpenSearchClient
        os_client = OpenSearchClient()
        if os_client.wait_for_availability(timeout_seconds=5):
            resp = os_client.client.search(
                index=os_client.index_name,
                body={"query": {"match_all": {}}, "size": 1000}
            )
            hits = resp["hits"]["hits"]
            print(f"Fetched {len(hits)} documents from OpenSearch.")
            
            # Let's count mentions of each deal in OpenSearch documents
            deal_matches = {deal: [] for deal in deals}
            for hit in hits:
                source = hit["_source"]
                doc_id = hit["_id"]
                file_name = source.get("file_name", "")
                file_path = source.get("file_path", "")
                main_content = source.get("main_content", "") or ""
                ocr_content = source.get("ocr_content", "") or ""
                embedded_content = source.get("embedded_content", "") or ""
                
                full_text = " ".join([file_name, file_path, main_content, ocr_content, embedded_content])
                
                for deal in deals:
                    if not deal or len(deal) < 2:
                        continue
                    # Regex matching with word boundaries
                    pattern = re.compile(r'\b' + re.escape(deal) + r'\b', re.IGNORECASE)
                    if pattern.search(full_text):
                        deal_matches[deal].append(file_name)
            
            print("\nDeal Match Results:")
            found_any = False
            for deal, matched_files in deal_matches.items():
                if matched_files:
                    found_any = True
                    print(f" - Deal '{deal}': found in {len(matched_files)} files: {matched_files[:3]}...")
            if not found_any:
                print("No divestiture deal names found in ANY document content!")
        else:
            print("OpenSearch not available")
    except Exception as e:
        print(f"Error checking OpenSearch: {e}")

    conn.close()

if __name__ == '__main__':
    main()
