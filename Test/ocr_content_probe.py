#!/usr/bin/env python3
"""Probe OCR'd documents to find ones with real text for accuracy testing."""
from opensearchpy import OpenSearch
os_client = OpenSearch(hosts=[{"host":"localhost","port":9200}], use_ssl=False, timeout=30)

# Find OCR'd docs with actual text content
resp = os_client.search(index="enterprise_documents", body={
    "size": 20,
    "query": {"bool": {"must": [
        {"term": {"ocr_completed": True}},
        {"range": {"ocr_confidence": {"gte": 40}}}
    ]}},
    "_source": ["file_name","ocr_content","ocr_confidence","file_path","mime_type"],
    "sort": [{"ocr_confidence": "desc"}]
})

print(f"Total OCR completed with conf>=40: {resp['hits']['total']['value']}")
print()
for i, hit in enumerate(resp["hits"]["hits"]):
    src = hit["_source"]
    ocr = src.get("ocr_content", "")
    fname = src.get("file_name", "?")
    conf = src.get("ocr_confidence", 0)
    fpath = src.get("file_path", "?")
    print(f"{i+1}. {fname}")
    print(f"   conf={conf}, text_len={len(ocr)}")
    print(f"   path={fpath[-80:]}")
    if ocr:
        preview = ocr[:200].replace("\n", " | ")
        print(f"   text: {preview}")
    print()

# Also check what field the text is stored in
print("\n--- Checking if text is in other fields ---")
resp2 = os_client.search(index="enterprise_documents", body={
    "size": 5,
    "query": {"bool": {"must": [
        {"term": {"ocr_completed": True}},
        {"range": {"ocr_confidence": {"gte": 80}}}
    ]}},
    "_source": True,
})
for hit in resp2["hits"]["hits"]:
    src = hit["_source"]
    fname = src.get("file_name", "?")
    print(f"\nFile: {fname}")
    for k, v in src.items():
        if isinstance(v, str) and len(v) > 20:
            print(f"  {k}: len={len(v)}, preview={v[:80]}")
        elif not isinstance(v, str):
            print(f"  {k}: {v}")
