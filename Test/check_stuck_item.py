import redis
import json
import requests

r = redis.Redis(decode_responses=True)

# Get stuck item
proc_key = 'docsearch:processing:indexing:indexing-3'
item_json = r.hget(proc_key, '1')
if item_json:
    item = json.loads(item_json)
    print(f"Stuck item file_id: {item['file_id']}")

# Get file metadata
meta = r.hgetall('docsearch:files:1')
print("\nFile 1 metadata:")
for k, v in sorted(meta.items()):
    print(f"  {k}: {v}")

# Check if in completed
in_completed = r.sismember('docsearch:completed_file_ids', '1')
print(f"\nIn completed_file_ids: {in_completed}")

# Check OpenSearch
file_hash = meta.get('file_hash', '')
if file_hash:
    resp = requests.get('http://localhost:9200/enterprise_documents/_search',
                       json={'query': {'term': {'file_hash': file_hash}}},
                       timeout=5)
    os_count = resp.json()['hits']['total']['value']
    print(f"In OpenSearch (by hash): {os_count}")

# Check if this is the duplicate
counter_discovered = int(r.get('docsearch:counter:discovered') or 0)
file_hashes_count = r.scard('docsearch:file_hashes')
print(f"\nDiscovered counter: {counter_discovered}")
print(f"Unique file hashes: {file_hashes_count}")
print(f"Race-condition duplicate: {counter_discovered - file_hashes_count}")
