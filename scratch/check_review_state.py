import sys, os
sys.path.insert(0, 'src')
os.chdir(r'c:\Users\DELL\Music\DocumentSearch')

from core.reporting_manager import get_docs_with_reviews, get_all_reviews_for_doc

docs = get_docs_with_reviews()
print(f'Total docs with reviews: {len(docs)}')
for d in docs:
    reviews = get_all_reviews_for_doc(d['smart_id'])
    types = {}
    for r in reviews:
        t = r.get('snippet_type','?')
        types[t] = types.get(t, 0) + 1
    statuses = {}
    for r in reviews:
        s = r.get('status', '?')
        statuses[s] = statuses.get(s, 0) + 1
    print(f"  {d['smart_id']}: {d['file_name']}")
    print(f"    reviews={len(reviews)}, types={types}, statuses={statuses}")
    if reviews:
        r = reviews[0]
        snippet_path = r.get('snippet_path','')
        print(f"    sample snippet_path: {snippet_path}")
        print(f"    snippet file exists: {os.path.exists(snippet_path)}")
        print(f"    accuracy_impact: {r.get('accuracy_impact')}")
        print(f"    reviewer_role: {r.get('reviewer_role')}")

# Check config for visual_allowed_types
import yaml
with open('config/config.yaml', 'r') as f:
    cfg = yaml.safe_load(f)

ocr_cfg = cfg.get('ocr', {}).get('preprocessing', {})
print("\n=== OCR Preprocessing Config ===")
print(f"  visual_allowed_types: {ocr_cfg.get('visual_allowed_types')}")
print(f"  signature_min_impact: {ocr_cfg.get('signature_min_impact')}")
print(f"  logo_min_impact: {ocr_cfg.get('logo_min_impact')}")
print(f"  stamp_min_impact: {ocr_cfg.get('stamp_min_impact')}")
print(f"  text_anomaly_min_impact: {ocr_cfg.get('text_anomaly_min_impact')}")
print(f"  review_keep_signatures: {ocr_cfg.get('review_keep_signatures')}")
print(f"  visual_pdf_overrides: {ocr_cfg.get('visual_pdf_overrides')}")
