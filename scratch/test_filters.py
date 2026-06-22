"""Test that the snippet review filters now work correctly with actual DB data."""
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, 'src')
os.chdir(r'c:\Users\DELL\Music\DocumentSearch')

from core.reporting_manager import get_docs_with_reviews, get_all_reviews_for_doc
from core.config_manager import get_config
from pathlib import Path

config = get_config()
preprocessing_cfg = dict(getattr(config.ocr, "preprocessing", {}) or {})
reviewer_roles_cfg = dict(getattr(config.ocr, "reviewer_roles", {}) or {})

print("=== Config Check ===")
print(f"visual_allowed_types: {preprocessing_cfg.get('visual_allowed_types')}")
print(f"stamp_min_impact: {preprocessing_cfg.get('stamp_min_impact')}")
print(f"signature_min_impact: {preprocessing_cfg.get('signature_min_impact')}")
print(f"reviewer_roles: {reviewer_roles_cfg}")

print("\n=== Per-doc snippet count (with new config) ===")
docs = get_docs_with_reviews()
total_visible = 0

for doc in docs:
    sid = doc['smart_id']
    all_snips = get_all_reviews_for_doc(sid)
    
    # Get dynamic role list
    known_roles = set(reviewer_roles_cfg.values())
    actual_roles = {s.get('reviewer_role','') for s in all_snips if s.get('reviewer_role')}
    all_roles = sorted(known_roles | actual_roles)
    
    # Apply allowed_types filter
    allowed_types = {str(t).strip().lower() for t in (preprocessing_cfg.get("visual_allowed_types") or [])}
    filtered = [s for s in all_snips if str(s.get("snippet_type","")).lower() in allowed_types]
    
    # Apply min_impact filter
    min_impact = {
        "signature": float(preprocessing_cfg.get("signature_min_impact", 0.0) or 0.0),
        "logo": float(preprocessing_cfg.get("logo_min_impact", 0.0) or 0.0),
        "stamp": float(preprocessing_cfg.get("stamp_min_impact", 0.0) or 0.0),
        "handwritten": float(preprocessing_cfg.get("handwritten_min_impact", 0.0) or 0.0),
        "text_anomaly": float(preprocessing_cfg.get("text_anomaly_min_impact", 0.0) or 0.0),
    }
    filtered = [s for s in filtered if float(s.get("accuracy_impact", 0.0) or 0.0) >= min_impact.get(str(s.get("snippet_type","")).lower(), 0.0)]
    
    print(f"\n{sid}: {doc['file_name']}")
    print(f"  All snippets: {len(all_snips)}")
    print(f"  After allowed_types+impact filter: {len(filtered)}")
    for s in filtered:
        print(f"    - type={s.get('snippet_type')} impact={s.get('accuracy_impact')} role={s.get('reviewer_role')} status={s.get('status')}")
    total_visible += len(filtered)
    print(f"  Dynamic roles: {all_roles}")

print(f"\n=== Total visible snippets: {total_visible} (was ~0 before fix) ===")
