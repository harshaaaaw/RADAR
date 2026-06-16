"""Check OCR configuration parameters."""
import sys
sys.path.insert(0, 'src')
from core.config_manager import get_config

config = get_config()
ocr = config.ocr

print("=== Tesseract Config ===")
print(f"  command: {ocr.tesseract.command}")
print(f"  timeout: {ocr.tesseract.timeout_seconds}s")  
print(f"  languages: {ocr.tesseract.languages}")
print(f"  engine_mode: {ocr.tesseract.engine_mode}")
print(f"  page_segmentation_mode: {ocr.tesseract.page_segmentation_mode}")

print("\n=== Smart Retries ===")
sr = getattr(ocr, 'smart_retries', {})
if hasattr(sr, 'enabled'):
    print(f"  enabled: {sr.enabled}")
    print(f"  min_confidence: {sr.min_confidence_threshold}")
elif isinstance(sr, dict):
    print(f"  enabled: {sr.get('enabled', False)}")
    print(f"  min_confidence: {sr.get('min_confidence_threshold', 80)}")
else:
    print(f"  raw: {sr}")

print("\n=== Preprocessing ===")
pp = ocr.preprocessing
print(f"  target_dpi: {pp.target_dpi}")
print(f"  grayscale: {pp.grayscale}")
print(f"  denoise: {pp.denoise}")
print(f"  deskew: {pp.deskew}")
print(f"  contrast_enhance: {pp.contrast_enhance}")

print("\n=== Other ===")
print(f"  min_confidence: {ocr.min_confidence}")
print(f"  max_pages_per_pdf: {getattr(ocr, 'max_pages_per_pdf', 'N/A')}")
