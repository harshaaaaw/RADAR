import sys
sys.path.insert(0, 'src')

from core.redis_queue_manager import RedisQueueManager
from core.constants import SizeCategory

qm = RedisQueueManager()

print("="*80)
print("CHECKING IF WORKERS CAN CLAIM WORK")
print("="*80)

# Try to claim work from each queue
for size_cat in [SizeCategory.SMALL, SizeCategory.MEDIUM]:
    print(f"\n🔍 Testing {size_cat.value} queue:")
    
    # Get current queue size
    queue_size_before = qm.get_extraction_queue_size(size_cat)
    print(f"   Queue size: {queue_size_before}")
    
    # Try to claim work
    work_items = qm.claim_extraction_work(
        size_category=size_cat,
        worker_id="TEST_WORKER",
        batch_size=1
    )
    
    if work_items:
        print(f"   ✅ Successfully claimed {len(work_items)} item(s)")
        print(f"   First item: {work_items[0].get('file_path', 'Unknown')[:60]}")
        
        # Put it back for now (we won't process it)
        # Note: In a real scenario, worker would process then complete
    else:
        print("   ❌ Could not claim work (queue returned empty)")

print("\n" + "="*80)
print("ROOT CAUSE DIAGNOSIS")
print("="*80)
print("\n🔍 If test worker CAN claim work:")
print("   Problem: Real workers are stuck/crashed/not polling")
print("\n🔍 If test worker CANNOT claim work:")
print("   Problem: Queue structure issue or items in wrong state")
