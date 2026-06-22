import sys
import os
import json
from pathlib import Path
from pdf2image import convert_from_path
import cv2
import numpy as np

sys.path.insert(0, os.path.abspath('src'))
sys.path.insert(0, os.path.abspath('.'))
from src.extraction.accuracy_analyzer import AccuracyAnalyzer
from src.ocr.ocr_worker import OCRWorker

def main():
    pdf_path = r"C:\Users\DELL\Downloads\DocumentSearch\test_data\real_funsd_form_011.pdf"
    if not os.path.exists(pdf_path):
        print("PDF file not found!")
        return

    print("PDF File path:", pdf_path)
    
    # 1. Convert PDF page 1 to image bytes
    pages = convert_from_path(
        pdf_path,
        dpi=300,
        poppler_path=r"C:\Users\DELL\Downloads\poppler-24.02.0\Library\bin"
    )
    if not pages:
        print("Failed to convert PDF to image")
        return
        
    page1 = pages[0]
    import io
    img_byte_arr = io.BytesIO()
    page1.save(img_byte_arr, format='PNG')
    img_bytes = img_byte_arr.getvalue()
    
    # 2. Run AccuracyAnalyzer segmenter
    analyzer = AccuracyAnalyzer(enable_yolo=False, enable_doctr=False) # Disable deep models first
    print("\n--- Running OpenCV Segmentation ---")
    zone_metrics = analyzer._segment_page_opencv(img_bytes)
    
    print("\nOpenCV Segmented zones metrics:")
    for k, v in zone_metrics.items():
        if k != 'bboxes':
            print(f"  {k}: {v}")
            
    print(f"\nOpenCV Bounding Boxes ({len(zone_metrics.get('bboxes', []))} found):")
    for idx, b in enumerate(zone_metrics.get('bboxes', [])):
        print(f"  {idx+1}: type={b['type']}, bbox={b['bbox']}, impact={b['impact']}")

    # 3. Detect faded text regions
    print("\n--- Running Faded Text Detection ---")
    faded_regions = analyzer._detect_faded_text_regions(img_bytes)
    print(f"Detected {len(faded_regions)} faded regions:")
    for idx, b in enumerate(faded_regions):
        print(f"  {idx+1}: type={b['type']}, bbox={b['bbox']}, impact={b['impact']}, density={b['ink_density']}")

    # 4. Run classification using OCRWorker classifier logic
    print("\n--- Running Refinement Classification ---")
    worker = OCRWorker(worker_id="debug-worker")
    
    # We need to mockup or load the PIL image
    from PIL import Image
    pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    w, h = pil_img.size
    
    all_bboxes = zone_metrics.get('bboxes', []) + faded_regions
    for idx, s in enumerate(all_bboxes):
        bbox = s["bbox"]
        cropped = pil_img.crop((bbox[0], bbox[1], bbox[2], bbox[3]))
        
        # Run classification
        refined_type, role = worker.classify_snippet_deficit(
            cropped_pil_img=cropped,
            bbox=bbox,
            page_dims=(w, h),
            initial_type=s["type"]
        )
        print(f"  {idx+1}: initial={s['type']} -> refined={refined_type}, role={role}, bbox={bbox}")

if __name__ == '__main__':
    main()
