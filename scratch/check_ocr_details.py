import sqlite3
import os
import json
import cv2
import numpy as np
from PIL import Image
import io
import pytesseract
from pathlib import Path
import sys

# Configure sys.path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from core.config_manager import get_config
from ocr.image_preprocessor_advanced import ImagePreprocessor

config = get_config()
try:
    tesseract_cmd = config.ocr.tesseract.command
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
except Exception:
    pass

def analyze_snippets():
    preprocessor = ImagePreprocessor()
    db_path = "runtime/audit/audit.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT review_id, snippet_type, snippet_path, bounding_box_json, accuracy_impact 
        FROM snippet_reviews 
        WHERE smart_id='DOC-20260617-E4D4'
    """)
    rows = cursor.fetchall()
    
    print(f"Loaded {len(rows)} snippet reviews from database.")
    
    results = []
    for row in rows:
        path = row["snippet_path"]
        review_id = row["review_id"]
        snippet_type = row["snippet_type"]
        bbox = json.loads(row["bounding_box_json"])
        
        if not path or not os.path.exists(path):
            results.append({
                "review_id": review_id,
                "type": snippet_type,
                "bbox": bbox,
                "status": "file_not_found"
            })
            continue
            
        # Read image
        img = cv2.imread(path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # OCR 1: Standard OCR on the crop
        txt_std = pytesseract.image_to_string(gray, config="--oem 1 --psm 6").strip()
        
        # OCR 2: System Preprocessed OCR
        # Convert crop image to bytes
        _, buffer = cv2.imencode('.png', img)
        crop_bytes = buffer.tobytes()
        
        # Run system advanced preprocessor
        preprocessed_bytes = preprocessor.preprocess(crop_bytes)
        if preprocessed_bytes:
            nparr = np.frombuffer(preprocessed_bytes, np.uint8)
            prep_img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
            txt_prep = pytesseract.image_to_string(prep_img, config="--oem 1 --psm 6").strip()
        else:
            txt_prep = ""
        
        # OCR 3: Grayscale with CLAHE
        clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        txt_enhanced = pytesseract.image_to_string(enhanced, config="--oem 1 --psm 6").strip()
        
        results.append({
            "review_id": review_id,
            "type": snippet_type,
            "filename": Path(path).name,
            "bbox": bbox,
            "txt_std": txt_std.replace("\n", " "),
            "txt_prep": txt_prep.replace("\n", " "),
            "txt_enhanced": txt_enhanced.replace("\n", " ")
        })
        
    conn.close()
    
    output_path = "scratch/snippet_ocr_analysis.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Analysis saved to {output_path}")

if __name__ == "__main__":
    analyze_snippets()
