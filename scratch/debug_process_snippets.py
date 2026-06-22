import sys
import os
import json
from pathlib import Path
from pdf2image import convert_from_path
import cv2
import numpy as np

sys.path.insert(0, os.path.abspath('src'))
sys.path.insert(0, os.path.abspath('.'))

from src.core.config_manager import get_config
from src.extraction.accuracy_analyzer import AccuracyAnalyzer
from src.ocr.ocr_worker import OCRWorker

def main():
    pdf_path = r"C:\Users\DELL\Downloads\DocumentSearch\test_data\real_funsd_form_011.pdf"
    if not os.path.exists(pdf_path):
        print("PDF file not found!")
        return

    pages = convert_from_path(
        pdf_path,
        dpi=300,
        poppler_path=r"C:\Users\DELL\Downloads\poppler-24.02.0\Library\bin"
    )
    page1 = pages[0]
    import io
    img_byte_arr = io.BytesIO()
    page1.save(img_byte_arr, format='PNG')
    img_bytes = img_byte_arr.getvalue()
    
    analyzer = AccuracyAnalyzer(enable_yolo=False, enable_doctr=False)
    zone_metrics = analyzer._segment_page_opencv(img_bytes)
    
    # Let's run faded text detection
    faded_regions = analyzer._detect_faded_text_regions(img_bytes)
    if "bboxes" not in zone_metrics:
        zone_metrics["bboxes"] = []
    zone_metrics["bboxes"].extend(faded_regions)
    
    # We will pass the JSON string of accuracy loss
    loss_breakdown = analyzer._build_loss_breakdown(
        zones=zone_metrics,
        tess={"processed_char_count": 100},
        doctr=None,
        estimated_total=1000
    )
    loss_json_str = json.dumps(loss_breakdown["accuracy_loss_breakdown"])
    
    # Now let's trace process_visual_snippets
    worker = OCRWorker(worker_id="debug-worker")
    
    # Let's trace it and print log messages
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("\n--- Running Trace on _process_visual_snippets ---")
    
    # We can write a custom trace to mimic _process_visual_snippets but printing info
    snippets = zone_metrics.get("bboxes", [])
    print(f"Total snippets initially: {len(snippets)}")
    
    # Let's see what allowed types are
    preprocessing_cfg = dict(getattr(worker.config.ocr, "preprocessing", {}) or {})
    allowed_types = {
        str(t).strip().lower()
        for t in (preprocessing_cfg.get("visual_allowed_types") or [])
        if str(t).strip()
    }
    print("Allowed types:", allowed_types)
    
    snippets_allowed = [
        s for s in snippets
        if str((s or {}).get("type", "logo")).lower() in allowed_types
    ]
    print(f"Snippets after allowed_types filter: {len(snippets_allowed)}")
    for s in snippets:
        t = str((s or {}).get("type", "logo")).lower()
        if t not in allowed_types:
            print(f"  Filtered out: type={t}, bbox={s['bbox']}")
            
    min_impact_by_type = {
        "signature": float(preprocessing_cfg.get("signature_min_impact", 0.0) or 0.0),
        "logo": float(preprocessing_cfg.get("logo_min_impact", 0.0) or 0.0),
        "stamp": float(preprocessing_cfg.get("stamp_min_impact", 0.0) or 0.0),
        "text_anomaly": float(preprocessing_cfg.get("text_anomaly_min_impact", 0.0) or 0.0),
    }
    print("Min impact:", min_impact_by_type)
    
    impact_filtered = []
    for s in snippets_allowed:
        s_type = str((s or {}).get("type", "logo")).lower()
        s_impact = float((s or {}).get("impact", 0.0) or 0.0)
        if s_impact >= min_impact_by_type.get(s_type, 0.0):
            impact_filtered.append(s)
        else:
            print(f"  Filtered by impact: type={s_type}, impact={s_impact}, limit={min_impact_by_type.get(s_type, 0.0)}")
            
    snippets = impact_filtered
    print(f"Snippets after impact filter: {len(snippets)}")
    
    # Let's do max per type
    max_per_type_cfg = preprocessing_cfg.get("max_per_page_per_type") or {}
    print("Max per page per type:", max_per_type_cfg)
    if isinstance(max_per_type_cfg, dict) and snippets:
        grouped = {}
        for s in snippets:
            s_type = str((s or {}).get("type", "logo")).lower()
            grouped.setdefault(s_type, []).append(s)
            
        topk_snippets = []
        for s_type, items in grouped.items():
            items_sorted = sorted(items, key=lambda it: float(it.get("impact", 0.0)), reverse=True)
            limit = int(max_per_type_cfg.get(s_type, 0) or 0)
            if limit > 0:
                print(f"  Limiting {s_type} to {limit} (had {len(items_sorted)})")
                items_sorted = items_sorted[:limit]
            topk_snippets.extend(items_sorted)
        snippets = topk_snippets
    print(f"Snippets after max_per_page filter: {len(snippets)}")
    
    # PIL image
    from PIL import Image
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    w, h = img.size
    
    # Let's trace each snippet's suppression
    for idx, snippet in enumerate(snippets, 1):
        snippet_type = snippet.get("type", "logo")
        bbox = snippet.get("bbox", [])
        impact = snippet.get("impact", 0.0)
        force_keep = bool(snippet.get("force_keep", False))
        
        print(f"\nProcessing snippet {idx}: type={snippet_type}, bbox={bbox}, impact={impact}, force_keep={force_keep}")
        
        x1, y1, x2, y2 = bbox
        x1 = max(0, min(int(x1), w - 1))
        y1 = max(0, min(int(y1), h - 1))
        x2 = max(x1 + 1, min(int(x2), w))
        y2 = max(y1 + 1, min(int(y2), h))
        box_w = max(1, x2 - x1)
        box_h = max(1, y2 - y1)
        width_ratio = box_w / max(1, w)
        height_ratio = box_h / max(1, h)
        aspect_ratio = box_w / max(1, box_h)
        
        # Heuristics
        is_likely_artifact = False
        if snippet_type == "signature":
            if height_ratio < 0.002 or width_ratio > 0.95 or aspect_ratio > 40.0:
                is_likely_artifact = True
                print("  Suppressed: artifact_heuristic (Rule 1: lines)")
            elif box_h < 4 or box_w < 4:
                is_likely_artifact = True
                print("  Suppressed: artifact_heuristic (Rule 2: tiny dots)")
            elif (box_w * box_h) < 16:
                is_likely_artifact = True
                print("  Suppressed: artifact_heuristic (Rule 3: small area)")
                
        if (not force_keep) and is_likely_artifact:
            continue
            
        # Crop and process
        from src.ocr.ocr_worker import _apply_crop_padding, _deskew_crop, _ensure_minimum_resolution
        px1, py1, px2, py2 = _apply_crop_padding(x1, y1, x2, y2, w, h)
        cropped = img.crop((px1, py1, px2, py2))
        cropped = _deskew_crop(cropped)
        cropped = _ensure_minimum_resolution(cropped)
        
        # Sparse noise
        if (not force_keep) and worker._is_sparse_noise_visual_snippet(cropped, snippet_type):
            print("  Suppressed: sparse_noise_filter")
            continue
            
        # Printed font
        if (not force_keep) and snippet_type == "signature" and worker._is_printed_font_snippet(cropped):
            print("  Suppressed: printed_font_classifier")
            continue
            
        # Save temp image for text-like classifier
        temp_path = f"scratch_snippet_temp_{idx}.png"
        cropped.save(temp_path)
        
        # Text-like
        if (not force_keep) and worker._is_text_like_visual_snippet(temp_path, snippet_type):
            print("  Suppressed: text_like_classifier")
            os.remove(temp_path)
            continue
            
        print("  -> KEPT! Refined type classification:")
        refined_type, role = worker.classify_snippet_deficit(cropped, bbox, (w, h), snippet_type)
        print(f"     Refined type: {refined_type}, role: {role}")
        os.remove(temp_path)

if __name__ == '__main__':
    main()
