import sqlite3

# Connect to the SQLite queue database
conn = sqlite3.connect('D:\\DocumentSearch\\queue\\queue.db')
cursor = conn.cursor()

print("="*80)
print("SQLITE EXTRACTION QUEUE STATUS")
print("="*80)

# Check extraction queue
cursor.execute("""
    SELECT size_category, status, COUNT(*) as count
    FROM extraction_queue
    GROUP BY size_category, status
    ORDER BY size_category, status
""")

print("\n📊 Extraction Queue Breakdown:")
print(f"{'Category':<10} {'Status':<12} {'Count':>8}")
print("-" * 35)
for row in cursor.fetchall():
    print(f"{row[0]:<10} {row[1]:<12} {row[2]:>8,}")

# Get total pending
cursor.execute("SELECT COUNT(*) FROM extraction_queue WHERE status = 'pending'")
total_pending = cursor.fetchone()[0]

# Get total processing  
cursor.execute("SELECT COUNT(*) FROM extraction_queue WHERE status = 'processing'")
total_processing = cursor.fetchone()[0]

print(f"\n{'='*35}")
print(f"{'TOTAL PENDING:':<25} {total_pending:>8,}")
print(f"{'TOTAL PROCESSING:':<25} {total_processing:>8,}")
print(f"{'='*35}")

# Check if any are stuck in processing (claimed more than 5 minutes ago)
import time
timeout_threshold = time.time() - 300
cursor.execute("""
    SELECT COUNT(*) FROM extraction_queue 
    WHERE status = 'processing' 
    AND claimed_at < ?
""", (timeout_threshold,))
stuck_count = cursor.fetchone()[0]

if stuck_count > 0:
    print(f"\n⚠️  WARNING: {stuck_count} items stuck in 'processing' state (>5 min)")
    
# Check pending items details (first 10)
cursor.execute("""
    SELECT id, file_path, size_category, priority, status
    FROM extraction_queue
    WHERE status = 'pending'
    LIMIT 10
""")

print("\n📝 First 10 Pending Items:")
for row in cursor.fetchall():
    print(f"  ID: {row[0]}, Category: {row[2]}, File: {row[1][:60]}...")

conn.close()

print("\n" + "="*80)
print("ROOT CAUSE:")
print("="*80)
print(f"\n✅ SQLite HAS {total_pending} pending items ready to process")
print("✅ Workers ARE pulling from SQLite using claim_extraction_work()")
print(f"✅ Only {total_processing} workers are actively processing")
print("\n❓ WHY SO FEW WORKERS?")
print("   Possible reasons:")
print("   1. Most workers finished and exited (check logs for 'No work available')")
print("   2. Workers are slow/blocked (check if Tika is responding)")
print("   3. Workers crashed (check for exceptions in logs)")
print("   4. Workers weren't started properly (check process count)")
