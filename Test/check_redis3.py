import sys
sys.path.insert(0, r'c:\Users\hp212560601\Desktop\DocumentSearch\DocumentSearch\src')
import redis

r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# Get some sample keys
keys_sample = r.randomkey() if hasattr(r, 'randomkey') else None
if not keys_sample:
    cursor = '0'
    cursor, keys = r.scan(cursor=0, count=20)
    print("Sample keys from Redis:")
    for key in keys:
        key_type = r.type(key)
        print(f"  {key} ({key_type})")
