import sys
sys.path.insert(0, r'c:\Users\hp212560601\Desktop\DocumentSearch\DocumentSearch\src')
import redis

r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# Check specific keys
print('Check docsearch:completed:')
exists = r.exists('docsearch:completed')
print(f'  exists: {exists}')
hlen = r.hlen('docsearch:completed')
print(f'  hlen: {hlen}')
key_type = r.type('docsearch:completed')
print(f'  type: {key_type}')

# Scan for non-file keys
print('\nAll non-file docsearch keys:')
cursor = 0
while True:
    cursor, keys = r.scan(cursor=cursor, match='docsearch:*', count=100)
    for k in keys:
        if not k.startswith('docsearch:files:'):
            key_type = r.type(k)
            if key_type == 'hash':
                count = r.hlen(k)
            elif key_type == 'zset':
                count = r.zcard(k)
            elif key_type == 'list':
                count = r.llen(k)
            else:
                count = 0
            print(f'  {k} ({key_type}): {count}')
    if cursor == 0:
        break
