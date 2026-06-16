
import os
import sys
import logging
from pathlib import Path

# Add project root and src to path
current_dir = Path(__file__).parent.absolute()
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(current_dir / "src"))

# Setup Logging to stdout for debug
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(message)s')

from src.ocr.ocr_worker import OCRWorker

def test_smart_ocr(image_path_str):
    print(f"\n{'='*50}")
    print(f"Testing SMART OCR on: {image_path_str}")
    print(f"{'='*50}\n")
    
    if not os.path.exists(image_path_str):
        print("File not found.")
        return

    # Initialize Worker (Mocked/Partial)
    try:
        # We need to ensure we don't start the loop, just init
        worker = OCRWorker("debug-worker-1")
        
        # Call the new method directly
        result = worker._process_image_file(image_path_str)
        
        if result:
            text, conf = result
            print(f"\n[SUCCESS] Final Result (Conf={conf:.2f}%):")
            print(f"Text Snippet: {text[:200]}...") 
        else:
            print("\n[FAIL] No result returned.")
            
    except Exception as e:
        print(f"CRASH: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Test on a file that likely requires smart strategies (e.g. shadow or inverted)
    target = r"C:\Users\DELL\Downloads\TestDocuments\stress_challenging_shadow_0.png" 
    # Or fallback to normal
    if not os.path.exists(target):
         target = r"C:\Users\DELL\Downloads\TestDocuments\stress_img_35.png"
         
    test_smart_ocr(target)
