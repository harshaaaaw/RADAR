import sys
sys.path.insert(0, 'src')

from core.queue_manager import get_queue_manager

qm = get_queue_manager()
stats = qm.get_queue_statistics()

print("\n" + "="*70)
print("LIVE SYSTEM STATUS")
print("="*70)

# Extraction
ext_total = stats.get('extraction_total', {})
print("\n📂 EXTRACTION:")
print(f"   Pending:    {ext_total.get('pending', 0):,}")
print(f"   Processing: {ext_total.get('processing', 0):,}")  
print(f"   Completed:  {ext_total.get('completed', 0):,}")
print(f"   Total:      {ext_total.get('total', 0):,}")

# Indexing
indexing = stats.get('indexing', {})
print("\n🗂️  INDEXING:")
print(f"   Pending:    {indexing.get('pending', 0):,}")
print(f"   Processing: {indexing.get('processing', 0):,}")
print(f"   Completed:  {indexing.get('completed', 0):,}")
print(f"   Total:      {indexing.get('total', 0):,}")

# OCR
ocr = stats.get('ocr', {})
print("\n🔍 OCR:")
print(f"   Pending:    {ocr.get('pending', 0):,}")
print(f"   Processing: {ocr.get('processing', 0):,}")
print(f"   Completed:  {ocr.get('completed', 0):,}")
print(f"   Total:      {ocr.get('total', 0):,}")

# Completed
completed = stats.get('completed', {})
print("\n✅ COMPLETED:")
print(f"   Total:      {completed.get('total_completed', 0):,}")
print(f"   Duplicates: {completed.get('duplicates', 0):,}")
print(f"   Avg Extract: {completed.get('avg_extraction_ms', 0):.0f} ms")
print(f"   Avg Index:   {completed.get('avg_indexing_ms', 0):.0f} ms")

# Failures
print(f"\n❌ FAILURES: {stats.get('total_failures', 0):,}")

print("\n" + "="*70)
