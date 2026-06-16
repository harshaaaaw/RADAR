import sys
sys.path.insert(0, 'src')

from core.queue_manager import get_queue_manager

qm = get_queue_manager()
stats = qm.get_queue_statistics()

print("\n=== Extraction Stats ===")
print(f"Extraction by category: {stats.get('extraction', {})}")
print(f"\nExtraction total: {stats.get('extraction_total', 'NOT FOUND!')}")

if 'extraction_total' in stats:
    ext_total = stats['extraction_total']
    print("\nExtraction Total Breakdown:")
    print(f"  Total: {ext_total.get('total', 0)}")
    print(f"  Pending: {ext_total.get('pending', 0)}")
    print(f"  Processing: {ext_total.get('processing', 0)}")
    print(f"  Completed: {ext_total.get('completed', 0)}")
