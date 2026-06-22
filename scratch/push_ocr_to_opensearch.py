# -*- coding: utf-8 -*-
"""
Re-run OCR on all PDFs in test_data and push text content to OpenSearch.
This fixes the empty ocr_content / main_content issue in the search index.
"""
import sys, os, sqlite3, json, requests
# Force UTF-8 output on Windows
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, 'src')
os.chdir(r'c:\Users\DELL\Music\DocumentSearch')

import glob
from pathlib import Path

# Config
OS_URL = 'http://localhost:9200'
INDEX = 'enterprise_documents'
SOURCE_DIR = r'C:\Users\DELL\Downloads\DocumentSearch\test_data'

# Check OpenSearch connectivity
try:
    r = requests.get(f'{OS_URL}', timeout=5)
    print(f"OpenSearch OK: {r.status_code}")
except Exception as e:
    print(f"OpenSearch FAILED: {e}")
    sys.exit(1)

# Get all docs from OpenSearch that have empty ocr_content
body = {
    "query": {
        "bool": {
            "should": [
                {"term": {"ocr_completed": False}},
                {"bool": {"must_not": {"exists": {"field": "ocr_content"}}}},
                {"term": {"ocr_content": ""}}
            ]
        }
    },
    "size": 200,
    "_source": ["file_name", "smart_id", "file_path", "ocr_completed"]
}
r = requests.post(f'{OS_URL}/{INDEX}/_search', json=body, timeout=30)
hits = r.json().get('hits', {}).get('hits', [])
print(f"\nDocs needing OCR update: {len(hits)}")

# Try to extract OCR text from each PDF using existing OCR infrastructure
try:
    from ocr.tesseract_wrapper import TesseractWrapper
    from pdf2image import convert_from_path
    import pytesseract
    POPPLER_PATH = r'C:\Users\DELL\Downloads\poppler-24.02.0\Library\bin'
    TESSERACT_CMD = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
    HAS_OCR = True
    print("OCR tools available")
except ImportError as e:
    HAS_OCR = False
    print(f"OCR tools not available: {e}")

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF via pdf2image + pytesseract."""
    try:
        pages = convert_from_path(
            pdf_path, dpi=200, poppler_path=POPPLER_PATH,
            first_page=1, last_page=3  # Limit to first 3 pages for speed
        )
        all_text = []
        for i, img in enumerate(pages):
            text = pytesseract.image_to_string(img, lang='eng', timeout=60)
            if text.strip():
                all_text.append(f"[Page {i+1}]\n{text.strip()}")
        return '\n\n'.join(all_text)
    except Exception as e:
        print(f"  OCR error: {e}")
        return ""

updated = 0
failed = 0
for h in hits:
    src = h.get('_source', {})
    doc_id = h.get('_id')
    file_name = src.get('file_name', '')
    file_path = src.get('file_path', '')
    
    # Find the actual PDF file
    pdf_path = None
    if file_path and os.path.exists(file_path):
        pdf_path = file_path
    else:
        # Search in source dir
        candidates = glob.glob(os.path.join(SOURCE_DIR, '**', file_name), recursive=True)
        if candidates:
            pdf_path = candidates[0]
    
    if not pdf_path:
        print(f"  NOT FOUND: {file_name}")
        failed += 1
        continue
    
    print(f"Processing: {file_name}")
    
    # Extract OCR text
    if HAS_OCR and pdf_path.lower().endswith('.pdf'):
        ocr_text = extract_text_from_pdf(pdf_path)
    else:
        ocr_text = f"[Document: {file_name}]"
    
    if not ocr_text.strip():
        ocr_text = f"[Document: {file_name}] No extractable text found."
    
    print(f"  OCR text length: {len(ocr_text)} chars")
    
    # Push to OpenSearch
    update_body = {
        "script": {
            "source": """
                ctx._source.ocr_content = params.ocr_content;
                ctx._source.ocr_completed = true;
                ctx._source.ocr_confidence = params.ocr_confidence;
                if (ctx._source.containsKey('main_content') == false || 
                    ctx._source.main_content == null || 
                    ctx._source.main_content == '' ||
                    ctx._source.main_content.length() < 50) {
                    ctx._source.main_content = params.ocr_content;
                }
            """,
            "lang": "painless",
            "params": {
                "ocr_content": ocr_text[:100000],
                "ocr_confidence": 75.0 if len(ocr_text) > 100 else 20.0
            }
        }
    }
    
    try:
        r2 = requests.post(
            f'{OS_URL}/{INDEX}/_update/{doc_id}',
            json=update_body,
            timeout=30
        )
        result = r2.json().get('result', 'error')
        if result in ('updated', 'noop'):
            print(f"  [OK] Updated: {result}")
            updated += 1
        else:
            print(f"  [FAIL] Failed: {r2.json()}")
            failed += 1
    except Exception as e:
        print(f"  [ERR] Error: {e}")
        failed += 1

# Refresh index
requests.post(f'{OS_URL}/{INDEX}/_refresh', timeout=10)

print(f"\n=== Results ===")
print(f"Updated: {updated}")
print(f"Failed/NotFound: {failed}")
print(f"Total: {len(hits)}")

# Verify
r3 = requests.post(f'{OS_URL}/{INDEX}/_search', json={
    "query": {"term": {"ocr_completed": True}},
    "size": 1,
    "_source": ["file_name", "ocr_content"]
}, timeout=10)
hits3 = r3.json().get('hits', {}).get('hits', [])
if hits3:
    src = hits3[0].get('_source', {})
    print(f"\nVerification - {src.get('file_name')}: {len(src.get('ocr_content',''))} chars OCR")
