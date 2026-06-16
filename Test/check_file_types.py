
import os
import redis
from collections import Counter

def check_types():
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    
    print("Sampling file types...")
    
    ext_counts = Counter()
    needs_ocr_counts = Counter()
    status_counts = Counter()
    sample_size = 0
    limit = 500
    
    cursor = '0'
    while cursor != 0:
        cursor, keys = r.scan(cursor=cursor, match="docsearch:files:*", count=1000)
        
        for key in keys:
            data = r.hgetall(key)
            name = data.get('name', '')
            ext = os.path.splitext(name)[1].lower()
            
            ext_counts[ext] += 1
            
            # Check if flags indicating OCR need exist
            # Note: 'needs_ocr' might not be a top-level field in HASH if stored in JSON blob?
            # RedisQueueManager stores metadata flat in Hash usually?
            # Let's check keys available
            if sample_size == 0:
                print(f"Sample Keys in File Hash: {list(data.keys())}")
            
            # Inference based on extension usually
            status_counts[data.get('status')] += 1
            
            sample_size += 1
            
        if sample_size >= limit: break

    print(f"\nSampled {sample_size} files.")
    print("\nExtension Distribution:")
    for ext, count in ext_counts.most_common(10):
        print(f"  {ext}: {count}")
        
    print("\nStatus Distribution:")
    for stat, count in status_counts.items():
        print(f"  {stat}: {count}")

if __name__ == "__main__":
    check_types()
