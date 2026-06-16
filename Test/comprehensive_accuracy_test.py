
import requests
import time
import sys

BASE_URL = "http://localhost:8080"

def search(query):
    try:
        response = requests.get(f"{BASE_URL}/search", params={"q": query, "limit": 5})
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Search failed: {e}")
    return {"results": [], "total": 0}

def verify_hit(results, expected_filename_part):
    for res in results.get('results', []):
        # Handle nested document structure
        doc_data = res.get('document', {})
        fname = doc_data.get('file_name', '')
        if expected_filename_part in fname:
            return True, res
    return False, None

def run_test():
    print("=== COMPREHENSIVE ACCURACY TEST ===")
    print("Waiting 10s for indexing (if just generated)...")
    time.sleep(10) # Give some time for indexing if running immediately after generation
    
    tests = [
        # 1. Rotated Images (90/180/270)
        {
            "name": "Rotated Image (90/180/270 deg)",
            "query": '"ROTATION TEST 25"', 
            "expected": "stress_challenging_rot",
            "id_check": "25"
        },
        # 2. Inverted Text (White on Black)
        {
            "name": "Inverted Text (White on Black)",
            "query": '"INVERTED TEST 25"',
            "expected": "stress_challenging_inv_25.png",
            "id_check": None
        },
        # 3. Shadowed/Noisy Images
        {
            "name": "Shadowed/Noisy Image",
            "query": '"SHADOW TEST 25"',
            "expected": "stress_challenging_shadow_25.png",
            "id_check": None
        },
        # 4. PDF with Embedded Image
        {
            "name": "PDF Indexing (Image-based)",
            "query": '"PDF IMAGE TEST 25"',
            "expected": "stress_challenging_pdf_25.pdf",
            "id_check": None
        },
        # 5. Deep Nested ZIP Content
        {
            "name": "Deep Nested ZIP Content",
            "query": '"Content inside zip 25"',
            "expected": "inner_text.txt", # Or the zip name if mapped differently, usually inner file
            "id_check": None
        },
        # 6. Standard DOCX
        {
            "name": "Standard DOCX Content",
            "query": '"Stress Test Document 25"',
            "expected": "stress_doc_25.docx",
            "id_check": None
        },
        # 7. Standard Text File
        {
            "name": "Standard Text File",
            "query": '"File ID: 25"',
            "expected": "stress_txt_25.txt",
            "id_check": None
        }
    ]
    
    passed = 0
    total = len(tests)
    
    for t in tests:
        print(f"\nTesting: {t['name']}")
        print(f"  Query: {t['query']}")
        
        # Retry logic
        found = False
        for attempt in range(3):
            res = search(t['query'])
            hit, doc = verify_hit(res, t['expected'])
            
            if hit:
                # Extra check if needed
                if t['id_check'] and t['id_check'] not in doc['file_name']:
                    continue
                    
                print(f"  PASS: Found {doc['file_name']} (Score: {doc['score']:.2f})")
                passed += 1
                found = True
                break
            else:
                if attempt < 2:
                    time.sleep(2)
        
        if not found:
            print(f"  FAIL: Expected {t['expected']} not found. Top results:")
            for r in res.get('results', [])[:3]:
                # Handle potential nested structure
                doc = r.get('document', r)
                fname = doc.get('file_name', 'UNKNOWN_FILE')
                print(f"    - {fname}")

    print("-" * 30)
    print(f"Results: {passed}/{total} passed.")
    
    if passed == total:
        print("SUCCESS: All complex formats and edge cases verified.")
        sys.exit(0)
    else:
        print("FAILURE: Some tests failed.")
        sys.exit(1)

if __name__ == "__main__":
    run_test()
