import sys
sys.path.insert(0, r'c:\Users\hp212560601\Desktop\DocumentSearch\DocumentSearch\src')
import redis

r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# Get some sample keys
print("Getting sample keys...")
cursor, keys = r.scan(cursor=0, count=30)
print(f"Got {len(keys)} keys")
for key in keys[:20]:
    key_type = r.type(key)
    print(f"  {key} ({key_type})")
