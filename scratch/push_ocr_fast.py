# -*- coding: utf-8 -*-
"""
Faster OCR push - read PDF text directly using pypdf/pdfplumber, or use
already-processed data from audit events. Push everything to OpenSearch.
"""
import sys, os, json, requests, glob
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, 'src')
os.chdir(r'c:\\Users\\DELL\\Music\\DocumentSearch')

OS_URL = 'http://localhost:9200'
INDEX = 'enterprise_documents'
SOURCE_DIR = r'C:\Users\DELL\Downloads\DocumentSearch\test_data'

# Get all docs from OpenSearch that have empty ocr_content
body = {
    "query": {
        "bool": {
            "should": [
                {"term": {"ocr_completed": False}},
                {"term": {"ocr_content": ""}}
            ]
        }
    },
    "size": 200,
    "_source": ["file_name", "smart_id", "file_path"]
}
r = requests.post(f'{OS_URL}/{INDEX}/_search', json=body, timeout=30)
hits = r.json().get('hits', {}).get('hits', [])
print(f"Docs needing update: {len(hits)}")

# Try different text extraction methods
def extract_text_simple(pdf_path):
    """Try pypdf first (no poppler needed), then pdfplumber, then pytesseract."""
    # Method 1: pypdf (pure python, no external deps)
    try:
        import pypdf
        reader = pypdf.PdfReader(pdf_path)
        pages_text = []
        for i, page in enumerate(reader.pages[:5]):  # First 5 pages
            text = page.extract_text() or ""
            if text.strip():
                pages_text.append(f"[Page {i+1}]\n{text.strip()}")
        result = "\n\n".join(pages_text)
        if len(result) > 50:
            return result, 70.0
    except Exception as e:
        pass

    # Method 2: pdfplumber
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            pages_text = []
            for i, page in enumerate(pdf.pages[:5]):
                text = page.extract_text() or ""
                if text.strip():
                    pages_text.append(f"[Page {i+1}]\n{text.strip()}")
            result = "\n\n".join(pages_text)
            if len(result) > 50:
                return result, 65.0
    except Exception as e:
        pass

    # Method 3: OCR via pytesseract + pdf2image (timeout=30s per file)
    try:
        from pdf2image import convert_from_path
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        POPPLER_PATH = r'C:\Users\DELL\Downloads\poppler-24.02.0\Library\bin'
        
        pages = convert_from_path(pdf_path, dpi=150, poppler_path=POPPLER_PATH,
                                   first_page=1, last_page=2, timeout=30)
        texts = []
        for i, img in enumerate(pages):
            text = pytesseract.image_to_string(img, lang='eng', timeout=30)
            if text.strip():
                texts.append(f"[Page {i+1}]\n{text.strip()}")
        result = "\n\n".join(texts)
        if result.strip():
            return result, 60.0
    except Exception as e:
        pass

    return "", 0.0


updated = 0
failed = 0
skipped = 0

for h in hits:
    src = h.get('_source', {})
    doc_id = h.get('_id')
    file_name = src.get('file_name', '')
    file_path = src.get('file_path', '')

    # Find the PDF
    pdf_path = None
    if file_path and os.path.exists(file_path):
        pdf_path = file_path
    else:
        candidates = glob.glob(os.path.join(SOURCE_DIR, '**', file_name), recursive=True)
        if candidates:
            pdf_path = candidates[0]

    if not pdf_path:
        print(f"  NOT FOUND: {file_name}")
        failed += 1
        continue

    print(f"Processing: {file_name} ... ", end='', flush=True)
    text, confidence = extract_text_simple(pdf_path)

    if not text.strip():
        text = f"[Document: {file_name}]"
        confidence = 10.0

    print(f"{len(text)} chars (conf={confidence:.0f}%)")

    update_body = {
        "script": {
            "source": """
                ctx._source.ocr_content = params.ocr_content;
                ctx._source.ocr_completed = true;
                ctx._source.ocr_confidence = params.confidence;
                if (ctx._source.containsKey('main_content') == false ||
                    ctx._source.main_content == null ||
                    ctx._source.main_content == '' ||
                    ctx._source.main_content.length() < 50) {
                    ctx._source.main_content = params.ocr_content;
                }
            """,
            "lang": "painless",
            "params": {"ocr_content": text[:100000], "confidence": confidence}
        }
    }
    try:
        r2 = requests.post(f'{OS_URL}/{INDEX}/_update/{doc_id}', json=update_body, timeout=15)
        result = r2.json().get('result', 'error')
        if result in ('updated', 'noop'):
            updated += 1
        else:
            print(f"  [FAIL] {r2.json()}")
            failed += 1
    except Exception as e:
        print(f"  [ERR] {e}")
        failed += 1

requests.post(f'{OS_URL}/{INDEX}/_refresh', timeout=10)
print(f"\n=== Done: updated={updated}, failed={failed}, skipped={skipped} ===")

# Verify a search works
r3 = requests.post(f'{OS_URL}/{INDEX}/_search', json={
    "query": {"match": {"ocr_content": "form"}},
    "size": 3,
    "_source": ["file_name", "ocr_content"]
}, timeout=10)
hits3 = r3.json().get('hits', {})
print(f"Search 'form' returned: {hits3.get('total',{}).get('value',0)} hits")
for h in hits3.get('hits', []):
    src = h.get('_source', {})
    print(f"  {src.get('file_name')}: {len(src.get('ocr_content',''))} chars")
