import sys
sys.path.insert(0, r'c:\Users\hp212560601\Desktop\DocumentSearch\DocumentSearch\src')
import redis

r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# Check all hash keys
print("Checking hashes:")
hashes = r.keys('pipeline:*')
for h in sorted(hashes):
    if not any(c in h for c in ['queue:', 'processing:', 'list:']):  # Skip queues
        count = r.hlen(h)
        if count > 0:
            print(f"  {h}: {count}")

# Get info about Redis db
info = r.info()
print("\nRedis DB Info:")
print(f"  DB 0 keys: {info.get('db0', {})}")
print(f"  Used memory: {info.get('used_memory_human')}")
