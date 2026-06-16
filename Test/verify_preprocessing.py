
import cv2
import numpy as np
import pytesseract
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))
from ocr.image_preprocessor_advanced import ImagePreprocessor

def create_base_image(text="TEST DOCUMENT\nORIENTATION & SKEW"):
    img = np.ones((800, 600), dtype=np.uint8) * 255
    
    # Draw text using CV2 (simpler than PIL for this)
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(img, "TOP SECRET - TEST DOCUMENT", (50, 100), font, 1, (0), 2)
    cv2.putText(img, "This document is used to test", (50, 150), font, 0.8, (0), 2)
    cv2.putText(img, "preprocessing capabilities.", (50, 200), font, 0.8, (0), 2)
    cv2.putText(img, "Rotation: 0", (50, 300), font, 1, (0), 2)
    
    # Add a box (for perspective/border testing)
    cv2.rectangle(img, (40, 40), (560, 760), (0), 5)
    
    return img

def apply_rotation(img, angle):
    if angle == 90:
        return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    elif angle == 180:
        return cv2.rotate(img, cv2.ROTATE_180)
    elif angle == 270:
        return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return img

def apply_inversion(img):
    return cv2.bitwise_not(img)

def apply_shadow(img):
    rows, cols = img.shape
    # Create a shadow mask (linear gradient)
    shadow = np.zeros((rows, cols), dtype=np.uint8)
    for i in range(cols):
        shadow[:, i] = int(255 * (i / cols) * 0.6) # Darken right side
    
    # Apply shadow
    res = img.copy().astype(np.int16)
    res = res - shadow
    res = np.clip(res, 0, 255).astype(np.uint8)
    return res

def test_preprocessing():
    print("=== Testing Advanced Preprocessing ===\n")
    preprocessor = ImagePreprocessor()
    
    # 1. Test Rotation
    print("Test 1: Rotation Correction (90 deg)...")
    base = create_base_image()
    rotated = apply_rotation(base, 90)
    _, buf = cv2.imencode('.png', rotated)
    
    processed_bytes = preprocessor.preprocess(buf.tobytes())
    processed_arr = np.frombuffer(processed_bytes, np.uint8)
    processed_img = cv2.imdecode(processed_arr, cv2.IMREAD_GRAYSCALE)
    
    # Check orientation using Tesseract OSD on RESULT
    try:
        # Tesseract OSD on result should be 0 (upright)
        osd = pytesseract.image_to_osd(processed_img)
        print(f"  Result OSD:\n{osd}")
        if "Rotate: 0" in osd:
            print("  PASS: Image successfully rotated back to upright.")
        else:
            print("  FAIL: Image not upright.")
    except Exception as e:
        print(f"  WARNING: Tesseract OSD failed on result: {e}")

    # 2. Test Inversion
    print("\nTest 2: Inverted Text (White on Black)...")
    inverted = apply_inversion(base)
    _, buf = cv2.imencode('.png', inverted)
    
    processed_bytes = preprocessor.preprocess(buf.tobytes())
    processed_arr = np.frombuffer(processed_bytes, np.uint8)
    processed_img = cv2.imdecode(processed_arr, cv2.IMREAD_GRAYSCALE)
    
    mean_val = np.mean(processed_img)
    print(f"  Result Mean Pixel Value: {mean_val:.1f} (Exp > 127)")
    if mean_val > 200:
        print("  PASS: Image successfully re-inverted (White background).")
    else:
        print("  FAIL: Image still dark.")

    # 3. Test Text Extraction (General Quality)
    print("\nTest 3: Text Extraction on Shadowed Image...")
    base = create_base_image()
    shadowed = apply_shadow(base)
    _, buf = cv2.imencode('.png', shadowed)
    
    processed_bytes = preprocessor.preprocess(buf.tobytes())
    
    processed_arr = np.frombuffer(processed_bytes, np.uint8)
    processed_img = cv2.imdecode(processed_arr, cv2.IMREAD_GRAYSCALE)
    print(f"  Result Stats - Mean: {np.mean(processed_img):.1f}, Std: {np.std(processed_img):.1f}")
    
    # Save to temp file for tesseract
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tf:
        tf.write(processed_bytes)
        tpath = tf.name
    
    try:
        # Pytesseract default might strip newlines, let's keep them
        text = pytesseract.image_to_string(tpath, config='--psm 6')
        print(f"  Extracted Text Preview: {text.strip()[:50].replace(chr(10), ' ')}...")
        if "TOP SECRET" in text and "preprocessing" in text:
            print("  PASS: Clean text extracted from shadowed image.")
        else:
            print("  FAIL: Text extraction poor.")
    finally:
        os.unlink(tpath)

if __name__ == "__main__":
    test_preprocessing()
