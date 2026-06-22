import sys, os, requests, json, sqlite3
sys.path.insert(0, 'src')
os.chdir(r'c:\Users\DELL\Music\DocumentSearch')

# Check OpenSearch - what fields do docs have?
body = {"query": {"match_all": {}}, "size": 5, "_source": ["file_name", "smart_id", "ocr_content", "ocr_completed", "ocr_confidence", "main_content", "pipeline_type"]}
r = requests.post('http://localhost:9200/enterprise_documents/_search', json=body, timeout=10)
hits = r.json().get('hits', {}).get('hits', [])
print("Sample docs from OpenSearch:")
for h in hits:
    src = h.get('_source', {})
    print(f"  {src.get('file_name')}")
    print(f"    ocr_completed: {src.get('ocr_completed')}")
    print(f"    ocr_confidence: {src.get('ocr_confidence')}")
    print(f"    ocr_content len: {len(src.get('ocr_content') or '')}")
    print(f"    main_content len: {len(src.get('main_content') or '')}")
    print(f"    pipeline_type: {src.get('pipeline_type')}")

# Check audit.db for processed docs
db_path = r'C:\Users\DELL\Music\DocumentSearch\runtime\audit\audit.db'
conn = sqlite3.connect(db_path)
rows = conn.execute("SELECT smart_id, file_name, pipeline_type, extraction_accuracy, current_status FROM documents LIMIT 10").fetchall()
print(f"\naudit.db documents:")
for row in rows:
    print(f"  {row}")
conn.close()

# Check if there are any OCR text files saved
import glob
ocr_txt = glob.glob(r'C:\Users\DELL\Music\DocumentSearch\runtime\**\*.txt', recursive=True)
print(f"\nOCR text files saved: {len(ocr_txt)}")
if ocr_txt:
    print(f"  Sample: {ocr_txt[0]}")
    with open(ocr_txt[0], encoding='utf-8', errors='ignore') as f:
        print(f"  Content preview: {f.read(200)}")
