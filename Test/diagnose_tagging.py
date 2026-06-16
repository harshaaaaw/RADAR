"""
Diagnose tagging accuracy: check what content test files actually have,
why columns are empty, and validate tagging against content.
"""
import sys, json
sys.path.insert(0, "src")
from indexing.opensearch_client import OpenSearchClient

os_client = OpenSearchClient()

# 1. Sample documents with empty tagging fields
print("=" * 70)
print("PART 1: Documents with EMPTY category (zero confidence)")
print("=" * 70)
resp = os_client.client.search(
    index=os_client.index_name,
    body={
        "size": 5,
        "_source": [
            "file_name", "file_type", "category", "department", "purpose",
            "dynamic_subtags", "key_names", "tagging_status",
            "tag_confidence_overall", "main_content", "ocr_content",
        ],
        "query": {
            "bool": {
                "must": [{"term": {"tag_confidence_overall": 0.0}}],
            }
        },
    },
)
for hit in resp["hits"]["hits"]:
    s = hit["_source"]
    mc = (s.get("main_content") or "")[:200]
    oc = (s.get("ocr_content") or "")[:200]
    print(f"\nFile: {s.get('file_name')} ({s.get('file_type')})")
    print(f"  Category: '{s.get('category', '')}' | Dept: '{s.get('department', '')}' | Purpose: '{s.get('purpose', '')}'")
    print(f"  Confidence: {s.get('tag_confidence_overall')}")
    print(f"  Status: {s.get('tagging_status')}")
    print(f"  Main content ({len(s.get('main_content',''))} chars): {mc!r}")
    print(f"  OCR content ({len(s.get('ocr_content',''))} chars): {oc!r}")

# 2. Sample documents with non-zero confidence
print("\n" + "=" * 70)
print("PART 2: Documents with NON-ZERO confidence (tagged)")
print("=" * 70)
resp2 = os_client.client.search(
    index=os_client.index_name,
    body={
        "size": 5,
        "_source": [
            "file_name", "file_type", "category", "department", "purpose",
            "dynamic_subtags", "key_names", "tagging_status",
            "tag_confidence_overall", "main_content", "ocr_content",
            "amount_found", "important_dates", "confidentiality",
        ],
        "query": {"range": {"tag_confidence_overall": {"gt": 0.0}}},
        "sort": [{"tag_confidence_overall": {"order": "desc"}}],
    },
)
for hit in resp2["hits"]["hits"]:
    s = hit["_source"]
    mc = (s.get("main_content") or "")[:300]
    print(f"\nFile: {s.get('file_name')} ({s.get('file_type')})")
    print(f"  Category: '{s.get('category')}' | Dept: '{s.get('department')}' | Purpose: '{s.get('purpose')}'")
    print(f"  Subtags: {s.get('dynamic_subtags', [])}")
    print(f"  Key Names: {s.get('key_names', [])}")
    print(f"  Amounts: {s.get('amount_found', '')}")
    print(f"  Dates: {s.get('important_dates', [])}")
    print(f"  Confidentiality: {s.get('confidentiality', '')}")
    print(f"  Confidence: {s.get('tag_confidence_overall')}")
    print(f"  Content preview: {mc!r}")

# 3. Analyze content quality across all docs
print("\n" + "=" * 70)
print("PART 3: Content quality analysis")
print("=" * 70)

# Count by content length
for field in ["main_content", "ocr_content"]:
    for threshold in [0, 10, 50, 100, 500]:
        count = os_client.client.count(
            index=os_client.index_name,
            body={"query": {"bool": {"must": [
                {"exists": {"field": field}},
                {"script": {"script": f"doc['{field}'].size() > 0 && doc['{field}'].value.length() > {threshold}"}}
            ]}}}
        ).get("count", "error")
        print(f"  {field} > {threshold} chars: {count}")

# 4. Distribution of categories
print("\n" + "=" * 70)
print("PART 4: Full tagging distribution")
print("=" * 70)
agg = os_client.client.search(
    index=os_client.index_name,
    body={
        "size": 0,
        "aggs": {
            "categories": {"terms": {"field": "category", "size": 30, "min_doc_count": 1}},
            "departments": {"terms": {"field": "department", "size": 30}},
            "purposes": {"terms": {"field": "purpose", "size": 30}},
            "file_types": {"terms": {"field": "file_type", "size": 30}},
            "statuses": {"terms": {"field": "tagging_status", "size": 10}},
            "has_subtags": {"filter": {"script": {"script": "doc.containsKey('dynamic_subtags') && doc['dynamic_subtags'].size() > 0"}}},
            "has_key_names": {"filter": {"script": {"script": "doc.containsKey('key_names') && doc['key_names'].size() > 0"}}},
        },
    },
)
for agg_name in ["categories", "departments", "purposes", "file_types", "statuses"]:
    print(f"\n{agg_name}:")
    for b in agg["aggregations"][agg_name]["buckets"]:
        print(f"  {b['key']}: {b['doc_count']}")

print(f"\nDocs with dynamic_subtags: {agg['aggregations']['has_subtags']['doc_count']}")
print(f"Docs with key_names: {agg['aggregations']['has_key_names']['doc_count']}")

total = os_client.client.count(index=os_client.index_name, body={"query": {"match_all": {}}})["count"]
print(f"\nTotal docs: {total}")
