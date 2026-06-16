"""
Clean up stale processing items
"""
import redis
import json
from datetime import datetime

r = redis.Redis(decode_responses=True)

print("=" * 70)
print("STALE PROCESSING ITEM CLEANUP")
print("=" * 70)

# Find all processing keys with items
stale_items = []
proc_keys = list(r.keys('docsearch:processing:*'))
print(f"\nScanning {len(proc_keys)} processing keys...")

for key in proc_keys:
    items = r.hgetall(key)
    for file_id, item_json in items.items():
        try:
            item = json.loads(item_json)
            # Check if file is actually completed (in OpenSearch but not in completed_file_ids)
            is_in_completed = r.sismember('docsearch:completed_file_ids', file_id)
            
            if not is_in_completed:
                # Check file metadata
                file_meta = r.hgetall(f'docsearch:files:{file_id}')
                status = file_meta.get('status', 'unknown')
                file_name = file_meta.get('file_name', 'unknown')
                file_hash = file_meta.get('file_hash', '')
                
                stale_items.append({
                    'key': key,
                    'file_id': file_id,
                    'file_name': file_name,
                    'file_hash': file_hash,
                    'status': status,
                    'item': item
                })
        except json.JSONDecodeError:
            pass

if stale_items:
    print(f"\n⚠ Found {len(stale_items)} stale processing items:")
    for item in stale_items:
        print(f"  file_id {item['file_id']}: {item['file_name']} (status: {item['status']})")
    
    # Clean them up
    print(f"\nCleaning up stale items...")
    for item in stale_items:
        r.hdel(item['key'], item['file_id'])
        print(f"  ✓ Removed file_id {item['file_id']} from {item['key']}")
    
    print(f"\n✓ Cleanup complete!")
else:
    print(f"\n✓ No stale items found")

# Verify
remaining = sum(r.hlen(k) for k in proc_keys)
print(f"\nRemaining processing items: {remaining}")
