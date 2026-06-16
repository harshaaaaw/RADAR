"""Quick exploration of indexed data for test design."""
import sys, os
sys.path.insert(0, "src")
os.environ["PYTHONIOENCODING"] = "utf-8"

from indexing.opensearch_client import OpenSearchClient
osc = OpenSearchClient()

# 1. File type distribution
print("=== FILE TYPE DISTRIBUTION ===")
r = osc.client.search(index=osc.index_name, body={"size":0,"aggs":{"types":{"terms":{"field":"file_type","size":20}}}})
for b in r["aggregations"]["types"]["buckets"]:
    print("  %s: %d" % (b["key"], b["doc_count"]))

# 2. Sample content
print("\n=== SAMPLE DOCUMENT CONTENT ===")
for name in ["sample1.txt", "sample2.txt", "stress_doc_0.docx", "stress_txt_0.txt"]:
    r2 = osc.client.search(index=osc.index_name, body={
        "size":1, "query":{"term":{"file_name": name}},
        "_source":["file_name","main_content","file_type","file_size_bytes"]
    })
    if r2["hits"]["hits"]:
        h = r2["hits"]["hits"][0]["_source"]
        mc = h.get("main_content","")
        print("\n--- %s (type=%s, size=%s) ---" % (h["file_name"], h.get("file_type","?"), h.get("file_size_bytes","?")))
        print("Content preview (%d chars): %s" % (len(mc), mc[:400]))
    else:
        print("\n--- %s: NOT FOUND ---" % name)

# 3. Check for PNG/PDF/image files indexed
print("\n=== IMAGE/PDF FILES IN INDEX ===")
for ext in ["png","pdf","jpg","jpeg","tiff"]:
    r3 = osc.client.search(index=osc.index_name, body={"size":0,"query":{"wildcard":{"file_name":"*."+ext}}})
    cnt = r3["hits"]["total"]["value"]
    if cnt > 0:
        print("  .%s files indexed: %d" % (ext, cnt))
    else:
        print("  .%s files: NONE" % ext)

# 4. Non-empty OCR content
print("\n=== DOCS WITH ACTUAL OCR CONTENT ===")
r4 = osc.client.search(index=osc.index_name, body={
    "size":5, "query":{"bool":{"must":[{"exists":{"field":"ocr_content"}},{"script":{"script":"doc['ocr_content'].size() > 0"}}]}}
})
print("  Total with non-empty OCR content:", r4["hits"]["total"]["value"])

# 5. Mapping check - what fields exist
print("\n=== INDEX FIELD MAPPING (top-level) ===")
mapping = osc.client.indices.get_mapping(index=osc.index_name)
props = mapping[osc.index_name]["mappings"]["properties"]
for field in sorted(props.keys()):
    ftype = props[field].get("type", props[field].get("properties","object"))
    print("  %s: %s" % (field, ftype))
