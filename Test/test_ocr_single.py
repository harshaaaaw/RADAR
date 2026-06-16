
import sys
sys.path.insert(0, "src")
from ocr.tesseract_wrapper import TesseractWrapper
import os

def test_ocr_single():
    tw = TesseractWrapper()
    img_path = r"C:\Users\DELL\Downloads\TestDocuments\stress_img_33.png"
    
    if not os.path.exists(img_path):
        print(f"File not found: {img_path}")
        return

    print(f"Testing OCR on: {img_path}")
    result = tw.extract_text(img_path)
    
    if result:
        text, conf = result
        print(f"Text length: {len(text)}")
        print(f"Confidence: {conf}")
        print(f"Text preview: {text[:100]}")
    else:
        print("OCR returned None")

if __name__ == "__main__":
    test_ocr_single()
