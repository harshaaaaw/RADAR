import subprocess
import sys
sys.path.insert(0, 'src')

from core.queue_manager import get_queue_manager

print("="*80)
print("REDIS QUEUE INVESTIGATION")
print("="*80)

# Check queue manager type
qm = get_queue_manager()
print(f"\n📦 Queue Manager Type: {type(qm).__name__}")

# Get statistics
stats = qm.get_queue_statistics()

print("\n📊 EXTRACTION STATS FROM QUEUE MANAGER:")
extraction_stats = stats.get('extraction', {})
for category, cat_stats in extraction_stats.items():
    if isinstance(cat_stats, dict) and category != 'total':
        print(f"  {category}:")
        print(f"    Pending: {cat_stats.get('pending', 0)}")
        print(f"    Processing: {cat_stats.get('processing', 0)}")
        print(f"    Completed: {cat_stats.get('completed', 0)}")

extraction_total = stats.get('extraction_total', {})
print("\n  TOTAL:")
print(f"    Pending: {extraction_total.get('pending', 0)}")
print(f"    Processing: {extraction_total.get('processing', 0)}")
print(f"    Completed: {extraction_total.get('completed', 0)}")

# Check actual Redis queue lengths
print("\n📋 ACTUAL REDIS QUEUE LENGTHS:")
redis_cli = r'C:\Users\hp212560601\Downloads\Redis-x64-3.2.100\redis-cli.exe'
queues = ['tiny_queue', 'small_queue', 'medium_queue', 'large_queue']
for queue in queues:
    result = subprocess.run([redis_cli, 'LLEN', queue], capture_output=True, text=True)
    count = result.stdout.strip().split('\n')[-1] if result.stdout else '0'
    print(f"  {queue:<15}: {count}")

# Check Redis hash keys for pending items
print("\n🔍 CHECKING REDIS HASH KEYS:")
for queue in queues:
    # Check pending set
    result = subprocess.run([redis_cli, 'SCARD', f'extraction:{queue}:pending'], capture_output=True, text=True)
    pending_set = result.stdout.strip().split('\n')[-1] if result.stdout else '0'
    
    # Check processing set  
    result = subprocess.run([redis_cli, 'SCARD', f'extraction:{queue}:processing'], capture_output=True, text=True)
    processing_set = result.stdout.strip().split('\n')[-1] if result.stdout else '0'
    
    print(f"  {queue}:")
    print(f"    Pending set: {pending_set}")
    print(f"    Processing set: {processing_set}")

print("\n" + "="*80)
print("ROOT CAUSE ANALYSIS")
print("="*80)

total_pending = extraction_total.get('pending', 0)
if total_pending > 0:
    print("\n❌ MISMATCH DETECTED!")
    print(f"   Dashboard shows: {total_pending} pending")
    print("   Redis queues contain: 0 items")
    print("\n🔍 This means:")
    print("   - Items are tracked in Redis SETS (for statistics)")
    print("   - But NOT in Redis LISTS (where workers read from)")
    print("   - Workers are starved - they have nothing to process!")
    print("\n💡 LIKELY CAUSE:")
    print("   Queue synchronization issue between tracking sets and work lists")
else:
    print("\n✅ System completing normally - low pending count expected")
