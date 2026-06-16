#!/usr/bin/env python3
"""
Migration Script - Populate counters from existing data

This script should be run ONCE after updating to the new code to populate
the counter keys from existing data. After running, the counters will be
accurate for the dashboard.

Run this script:
    python scripts/migrate_counters.py
"""

import sys
from pathlib import Path

# Ensure src directory is importable
PROJECT_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.queue_manager import get_queue_manager


def migrate_counters():
    """Populate counter keys from existing data"""
    print("="*60)
    print("  COUNTER MIGRATION SCRIPT")
    print("="*60)
    
    qm = get_queue_manager()
    
    # Check current counter values
    current_discovered = int(qm.client.get(qm.COUNTER_DISCOVERED) or 0)
    current_bytes = int(qm.client.get(qm.COUNTER_DISCOVERED_BYTES) or 0)
    current_extraction = int(qm.client.get(qm.COUNTER_EXTRACTION_COMPLETED) or 0)
    
    print("\n  Current counter values:")
    print(f"    COUNTER_DISCOVERED: {current_discovered:,}")
    print(f"    COUNTER_DISCOVERED_BYTES: {current_bytes:,}")
    print(f"    COUNTER_EXTRACTION_COMPLETED: {current_extraction:,}")
    
    if current_discovered > 0:
        print("\n  ⚠️  Counters already have data. Migration may cause inaccurate counts.")
        response = input("  Continue anyway? (y/n): ").strip().lower()
        if response != 'y':
            print("  Migration cancelled.")
            return
    
    print("\n  Scanning existing data...")
    
    # Count discovered files by scanning HASH_FILES
    total_discovered_files = 0
    total_discovered_bytes = 0
    cursor = '0'
    
    while True:
        cursor, keys = qm.client.scan(cursor=cursor, match=f"{qm.HASH_FILES}:*", count=500)
        for key in keys:
            try:
                file_size = qm.client.hget(key, 'file_size')
                if file_size:
                    total_discovered_files += 1
                    total_discovered_bytes += int(file_size)
            except:
                pass
        
        if total_discovered_files % 5000 == 0 and total_discovered_files > 0:
            print(f"    Scanned {total_discovered_files:,} files...")
        
        if cursor == 0 or cursor == b'0':
            break
    
    print("\n  Found from HASH_FILES:")
    print(f"    Files: {total_discovered_files:,}")
    print(f"    Bytes: {total_discovered_bytes:,}")
    
    # Count extraction completed (use completed files as proxy since they all went through extraction)
    total_completed = qm.client.hlen(qm.HASH_COMPLETED)
    print(f"\n  Completed files (extraction done): {total_completed:,}")
    
    # Also count files in discovery queue (these were discovered but not in HASH_FILES anymore)
    discovery_pending = qm.client.zcard(qm.QUEUE_DISCOVERY)
    
    # Calculate total discovered = files in HASH_FILES + files in discovery queue
    # Actually, files in discovery queue ARE in HASH_FILES, so we shouldn't double count
    # The discovery queue contains file_ids that reference HASH_FILES entries
    
    print("\n  Setting counters...")
    
    # Set the counters
    pipe = qm.client.pipeline()
    pipe.set(qm.COUNTER_DISCOVERED, total_discovered_files)
    pipe.set(qm.COUNTER_DISCOVERED_BYTES, total_discovered_bytes)
    pipe.set(qm.COUNTER_EXTRACTION_COMPLETED, total_completed)
    pipe.execute()
    
    print("\n  ✓ Counters updated!")
    print(f"    COUNTER_DISCOVERED: {total_discovered_files:,}")
    print(f"    COUNTER_DISCOVERED_BYTES: {total_discovered_bytes:,}")
    print(f"    COUNTER_EXTRACTION_COMPLETED: {total_completed:,}")
    
    # Verify
    print("\n  Verifying...")
    new_discovered = int(qm.client.get(qm.COUNTER_DISCOVERED) or 0)
    new_bytes = int(qm.client.get(qm.COUNTER_DISCOVERED_BYTES) or 0)
    new_extraction = int(qm.client.get(qm.COUNTER_EXTRACTION_COMPLETED) or 0)
    
    print(f"    COUNTER_DISCOVERED: {new_discovered:,} {'✓' if new_discovered == total_discovered_files else '✗'}")
    print(f"    COUNTER_DISCOVERED_BYTES: {new_bytes:,} {'✓' if new_bytes == total_discovered_bytes else '✗'}")
    print(f"    COUNTER_EXTRACTION_COMPLETED: {new_extraction:,} {'✓' if new_extraction == total_completed else '✗'}")
    
    print("\n" + "="*60)
    print("  Migration complete!")
    print("="*60 + "\n")


if __name__ == "__main__":
    migrate_counters()
