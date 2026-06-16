import sys
import json
sys.path.insert(0, r'c:\Users\hp212560601\Desktop\DocumentSearch\DocumentSearch\src')
import redis

r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# Get a sample completed file
cursor, data = r.hscan('docsearch:completed', 0, count=1)
for file_hash, info_json in data.items():
    info = json.loads(info_json)
    print('Sample completed file fields:')
    for key in sorted(info.keys()):
        val = str(info[key])[:80]
        print(f'  {key}: {val}')
    break
