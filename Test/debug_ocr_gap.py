
import os
import sys
sys.path.insert(0, "src")
from indexing.opensearch_client import OpenSearchClient
from core.config_manager import get_config

def debug_ocr_gap():
    osc = OpenSearchClient()
    
    # 1. Search for images/pdfs with NO ocr_content or confidence=0
    query = {
        "size": 20,
        "_source": ["file_name", "file_path", "file_type", "file_size", "needs_ocr", "ocr_completed", "ocr_confidence"],
        "query": {
            "bool": {
                "must": [
                    {"terms": {"file_type": ["png", "pdf", "jpeg", "jpg"]}}
                ],
                "must_not": [
                    {"range": {"ocr_confidence": {"gt": 0}}}
                ]
            }
        }
    }
    
    print("Searching for images with no OCR confidence...")
    r = osc.client.search(index=osc.index_name, body=query)
    hits = r["hits"]["hits"]
    total = r["hits"]["total"]["value"]
    print(f"Found {total} images missing OCR.")
    
    print("\n--- SAMPLE MISSING OCR FILES ---")
    for h in hits:
        src = h["_source"]
        print(f"File: {src.get('file_name')} ({src.get('file_type')})")
        print(f"  Path: {src.get('file_path')}")
        print(f"  Size: {src.get('file_size')}")
        print(f"  Needs OCR: {src.get('needs_ocr')}")
        print(f"  OCR Completed: {src.get('ocr_completed')}")
        print(f"  OCR Confidence: {src.get('ocr_confidence')}")
        print("-" * 40)

if __name__ == "__main__":
    debug_ocr_gap()
