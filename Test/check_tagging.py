"""Verify multiselect filter and aggregation logic works correctly."""
import sys
sys.path.insert(0, "src")
from indexing.opensearch_client import OpenSearchClient

os_client = OpenSearchClient()

# 1. Test aggregation (what _cached_filter_options does)
print("=== TESTING AGGREGATIONS (same as multiselect options) ===")

for field in ["file_type", "category", "department", "purpose"]:
    agg_query = {
        "size": 0,
        "aggs": {
            "unique_values": {
                "terms": {"field": field, "size": 100, "order": {"_key": "asc"}}
            }
        },
    }
    resp = os_client.client.search(index=os_client.index_name, body=agg_query)
    buckets = resp.get("aggregations", {}).get("unique_values", {}).get("buckets", [])
    values = [b["key"] for b in buckets if b.get("key")]
    print(f"\n{field}: {len(values)} unique values")
    for v in values[:10]:
        count = next(b["doc_count"] for b in buckets if b["key"] == v)
        print(f"  - {v} ({count})")

# 2. Test filter injection (same as perform_search with filters)
print("\n=== TESTING SEARCH WITH FILTER ===")
filter_query = {
    "query": {
        "bool": {
            "must": {"match_all": {}},
            "filter": [
                {"terms": {"category": ["Report"]}}
            ]
        }
    },
    "size": 3,
    "_source": ["file_name", "category", "department"]
}
resp = os_client.client.search(index=os_client.index_name, body=filter_query)
print(f"Results with category='Report': {resp['hits']['total']['value']}")
for hit in resp["hits"]["hits"]:
    s = hit["_source"]
    print(f"  {s.get('file_name')} - cat={s.get('category')} dept={s.get('department')}")

# 3. Get current queue stats (matches dashboard)
from core.queue_manager import get_queue_manager
qm = get_queue_manager()
stats = qm.get_queue_statistics()
size_stats = qm.get_size_statistics()

print("\n=== CURRENT DASHBOARD NUMBERS ===")
print(f"Discovery: total={stats['discovery']['total']}, completed={stats['discovery']['completed']}")
print(f"Extraction: total={stats['extraction_total']['total']}, pending={stats['extraction_total']['pending']}, completed={stats['extraction_total']['completed']}")
print(f"Indexing: total={stats['indexing']['total']}, pending={stats['indexing']['pending']}, processing={stats['indexing']['processing']}, completed={stats['indexing']['completed']}")
print(f"OCR: total={stats['ocr']['total']}, pending={stats['ocr']['pending']}, completed={stats['ocr']['completed']}")
print(f"Tagging: total={stats['tagging']['total']}, pending={stats['tagging']['pending']}, completed={stats['tagging']['completed']}")
print(f"Completed: {stats['completed']['total_completed']}")
print(f"\nSize stats:")
d = size_stats.get('discovered', {})
p = size_stats.get('in_pipeline', {})
s = size_stats.get('searchable', {})
f = size_stats.get('failed', {})
print(f"  Discovered: {d.get('files',0)} files / {d.get('size_bytes',0)} bytes")
print(f"  In Pipeline: {p.get('files',0)} files / {p.get('size_bytes',0)} bytes")
print(f"  Searchable: {s.get('files',0)} files ({s.get('items',0)} items) / {s.get('size_bytes',0)} bytes")
print(f"  Failed: {f.get('files',0)} files")
print(f"\nExpected dashboard progress: {s.get('files',0)}/{d.get('files',0)} = {s.get('files',0)/max(d.get('files',1),1)*100:.1f}%")
