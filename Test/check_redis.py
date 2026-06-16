import sys
sys.path.insert(0, r'c:\Users\hp212560601\Desktop\DocumentSearch\DocumentSearch\src')
import redis

# Create fresh instance
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# Check all keys  
keys = r.keys('pipeline:*')
print(f'All pipeline keys: {len(keys)} total')
for k in sorted(keys)[:20]:
    print(f'  {k}')

# Check count
print(f'\npipeline:completed count: {r.hlen("pipeline:completed")}')
print(f'pipeline:files (hash) count: {r.hlen("pipeline:files")}')

# Check size of important hashes
for key in ['pipeline:completed', 'pipeline:files', 'pipeline:discovery']:
    count = r.hlen(key)
    print(f'{key}: {count}')
