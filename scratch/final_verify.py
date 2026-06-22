# -*- coding: utf-8 -*-
"""Final end-to-end verification of all fixes."""
import sys, os, requests
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, 'src')
os.chdir(r'c:\Users\DELL\Music\DocumentSearch')

OS_URL = 'http://localhost:9200'
INDEX = 'enterprise_documents'

print("=" * 60)
print("FINAL SYSTEM VERIFICATION")
print("=" * 60)

# 1. OpenSearch stats
r = requests.post(f'{OS_URL}/{INDEX}/_search', json={
    "query": {"match_all": {}},
    "size": 0,
    "aggs": {
        "ocr_done": {"filter": {"term": {"ocr_completed": True}}},
        "has_content": {"filter": {"range": {"ocr_content": {"gt": ""}}}}
    }
}, timeout=10)
data = r.json()
total = data.get('hits', {}).get('total', {}).get('value', 0)
ocr_done = data.get('aggregations', {}).get('ocr_done', {}).get('doc_count', 0)
print(f"\n[SEARCH] OpenSearch Index:")
print(f"  Total docs: {total}")
print(f"  OCR completed: {ocr_done}")

# 2. Test multiple searches
queries = ["form", "date", "name", "amount", "address"]
print(f"\n[SEARCH] Test queries:")
for q in queries:
    r2 = requests.post(f'{OS_URL}/{INDEX}/_search', json={
        "query": {"multi_match": {"query": q, "fields": ["main_content", "ocr_content", "file_name"]}},
        "size": 3, "_source": ["file_name"]
    }, timeout=10)
    hits = r2.json().get('hits', {}).get('total', {}).get('value', 0)
    print(f"  '{q}' -> {hits} results")

# 3. Snippet review state
from core.reporting_manager import get_docs_with_reviews, get_all_reviews_for_doc
from core.config_manager import get_config
config = get_config()
preprocessing_cfg = dict(getattr(config.ocr, "preprocessing", {}) or {})

docs = get_docs_with_reviews()
print(f"\n[SNIPPET REVIEW] Documents with reviews: {len(docs)}")

total_visible = 0
allowed_types = {str(t).strip().lower() for t in (preprocessing_cfg.get("visual_allowed_types") or [])}
for doc in docs:
    snips = get_all_reviews_for_doc(doc['smart_id'])
    filtered = [s for s in snips if str(s.get('snippet_type','')).lower() in allowed_types]
    pending = [s for s in filtered if s.get('status') == 'pending']
    total_visible += len(filtered)
    status_icon = "RED" if pending else "GRN"
    print(f"  [{status_icon}] {doc['file_name']}: {len(filtered)} visible snippets ({len(pending)} pending)")

print(f"\n  Total visible snippets: {total_visible} (config filter: {allowed_types})")
print(f"  stamp_min_impact: {preprocessing_cfg.get('stamp_min_impact')}")
print(f"  signature_min_impact: {preprocessing_cfg.get('signature_min_impact')}")

# 4. Config role check
reviewer_roles_cfg = dict(getattr(config.ocr, "reviewer_roles", {}) or {})
all_docs_roles = set()
for doc in docs:
    snips = get_all_reviews_for_doc(doc['smart_id'])
    for s in snips:
        if s.get('reviewer_role'):
            all_docs_roles.add(s.get('reviewer_role'))
print(f"\n[ROLES] Actual reviewer roles in DB: {sorted(all_docs_roles)}")
print(f"  Config roles (from config.ocr.reviewer_roles): {reviewer_roles_cfg}")
print(f"  NOTE: Dynamic dropdown will show all roles found in DB automatically")

print("\n" + "=" * 60)
print("ALL CHECKS COMPLETE")
print("=" * 60)
