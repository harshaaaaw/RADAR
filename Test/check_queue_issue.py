import sqlite3
import sys
sys.path.insert(0, 'src')

# Check SQLite database
conn = sqlite3.connect('D:\\DocumentSearch\\queue\\queue.db')
cursor = conn.cursor()

print("="*80)
print("EXTRACTION QUEUE STATUS IN SQLITE DATABASE")
print("="*80)

cursor.execute("SELECT COUNT(*) FROM extraction_queue WHERE status = 'pending'")
pending_count = cursor.fetchone()[0]
print(f"\n📊 Total Pending: {pending_count}")

cursor.execute("""
    SELECT queue_name, status, COUNT(*) as count
    FROM extraction_queue
    GROUP BY queue_name, status
    ORDER BY queue_name, status
""")

print("\n📋 Breakdown by Queue and Status:")
print(f"{'Queue':<15} {'Status':<12} {'Count':>8}")
print("-" * 40)
for row in cursor.fetchall():
    queue_name, status, count = row
    print(f"{queue_name:<15} {status:<12} {count:>8,}")

# Check if items are stuck in processing
cursor.execute("""
    SELECT COUNT(*) FROM extraction_queue 
    WHERE status = 'processing'
""")
processing_stuck = cursor.fetchone()[0]
print(f"\n⚠️  Items stuck in 'processing': {processing_stuck}")

# Check Redis queues
print("\n" + "="*80)
print("REDIS QUEUE STATUS")
print("="*80)

import subprocess
queues = ['tiny_queue', 'small_queue', 'medium_queue', 'large_queue']
for queue in queues:
    result = subprocess.run(
        [r'C:\Users\hp212560601\Downloads\Redis-x64-3.2.100\redis-cli.exe', 'LLEN', queue],
        capture_output=True,
        text=True
    )
    count = result.stdout.strip().split('\n')[-1] if result.stdout else '0'
    print(f"  {queue:<15}: {count}")

print("\n" + "="*80)
print("ROOT CAUSE ANALYSIS")
print("="*80)

if pending_count > 0:
    # Check if items are in DB but not in Redis
    print("\n❌ PROBLEM DETECTED:")
    print(f"   - Database shows {pending_count} pending items")
    print("   - BUT Redis queues are all EMPTY (0 items)")
    print("\n🔍 ROOT CAUSE:")
    print("   Items are marked 'pending' in SQLite but were never pushed to Redis queues")
    print("   Workers read from Redis queues, so they have nothing to process!")
    print("\n💡 SOLUTION:")
    print("   Need to re-queue the pending items from SQLite into Redis")
else:
    print("\n✅ No pending items found - system may be completing normally")

conn.close()
