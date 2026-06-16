"""Investigate failed files - get breakdown and random samples"""
import sys
import json
import random
sys.path.insert(0, 'src')
from core.queue_manager import get_queue_manager

qm = get_queue_manager()

# Get all failed files
failed = []
cursor = 0
while True:
    cursor, data = qm.client.hscan('docsearch:failed', cursor, count=200)
    for fid, info_json in data.items():
        try:
            info = json.loads(info_json)
            failed.append(info)
        except:
            pass
    if cursor == 0:
        break

print(f"Total failed: {len(failed)}")

# Group by error type
from collections import Counter
types = Counter(f.get('error_type', 'unknown') for f in failed)
print(f"By type: {dict(types)}")

# Group by stage
stages = Counter(f.get('stage', 'unknown') for f in failed)
print(f"By stage: {dict(stages)}")

# Show 10 random samples
random.seed(42)
samples = random.sample(failed, min(10, len(failed)))
for i, s in enumerate(samples):
    fp = s.get('file_path', '?')
    et = s.get('error_type', '?')
    stg = s.get('stage', '?')
    msg = s.get('error_message', '')[:300]
    ext = fp.rsplit('.', 1)[-1].lower() if '.' in fp else 'none'
    print(f"\n--- Sample {i+1} ---")
    print(f"  extension: .{ext}")
    print(f"  file_path: {fp}")
    print(f"  error_type: {et}")
    print(f"  stage: {stg}")
    print(f"  error_message: {msg}")

# Show OCR errors specifically
ocr_errors = [f for f in failed if f.get('error_type') == 'ocr_error']
print(f"\n\n=== OCR ERRORS ({len(ocr_errors)}) ===")
for i, s in enumerate(ocr_errors[:10]):
    fp = s.get('file_path', '?')
    msg = s.get('error_message', '')[:300]
    ext = fp.rsplit('.', 1)[-1].lower() if '.' in fp else 'none'
    print(f"\n  OCR Error {i+1}: .{ext} - {fp}")
    print(f"  message: {msg}")

# Show indexing errors
idx_errors = [f for f in failed if f.get('error_type') == 'indexing_error']
print(f"\n\n=== INDEXING ERRORS ({len(idx_errors)}) ===")
for s in idx_errors:
    fp = s.get('file_path', '?')
    msg = s.get('error_message', '')[:400]
    print(f"\n  Indexing Error: {fp}")
    print(f"  message: {msg}")

# Show extraction errors by file extension
ext_errors = [f for f in failed if f.get('error_type') == 'extraction_failed']
ext_types = Counter()
for f in ext_errors:
    fp = f.get('file_path', '')
    ext = fp.rsplit('.', 1)[-1].lower() if '.' in fp else 'none'
    ext_types[ext] += 1
print(f"\n\n=== EXTRACTION FAILURES BY EXTENSION ({len(ext_errors)} total) ===")
for ext, count in ext_types.most_common(20):
    print(f"  .{ext}: {count}")

# Show some extraction error messages
print("\n=== SAMPLE EXTRACTION ERROR MESSAGES ===")
for s in random.sample(ext_errors, min(5, len(ext_errors))):
    fp = s.get('file_path', '?')
    msg = s.get('error_message', '')[:300]
    print(f"\n  {fp}")
    print(f"  -> {msg}")
