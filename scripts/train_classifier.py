import sqlite3
import os
import pickle
import numpy as np
from pathlib import Path
import sys

# Add src directory to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from ocr.visual_memory import VisualMemoryEngine
from core.config_manager import get_config

def train_classifier():
    print("Initializing VisualMemoryEngine...")
    engine = VisualMemoryEngine()
    
    db_path = "runtime/audit/audit.db"
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return
        
    print(f"Connecting to database {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT snippet_path, snippet_type FROM snippet_reviews")
    rows = cursor.fetchall()
    
    print(f"Found {len(rows)} snippet records in database.")
    
    X = []
    y = []
    
    # Track class distribution
    class_counts = {}
    
    for idx, (path, label) in enumerate(rows, 1):
        if not path or not os.path.exists(path):
            continue
            
        try:
            vector = engine.extract_vector(path)
            if vector is not None:
                X.append(vector)
                y.append(label)
                class_counts[label] = class_counts.get(label, 0) + 1
        except Exception as e:
            print(f"Failed to extract features for {path}: {e}")
            
        if idx % 20 == 0:
            print(f"  Processed {idx}/{len(rows)} crops...")
            
    conn.close()
    
    if len(X) < 10:
        print(f"Insufficient training data: only {len(X)} valid samples found.")
        return
        
    print("\nClass distribution:")
    for label, count in class_counts.items():
        print(f"  - {label}: {count}")
        
    if len(class_counts) < 2:
        print("Need at least 2 distinct classes to train SVM classifier.")
        return
        
    X = np.array(X)
    y = np.array(y)
    
    print(f"\nTraining Support Vector Machine (SVM) classifier on shape {X.shape}...")
    from sklearn.svm import SVC
    
    # Use SVC with RBF kernel and probability estimates enabled
    clf = SVC(C=1.0, kernel='rbf', probability=True, random_state=42)
    clf.fit(X, y)
    
    model_dir = Path("models")
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "snippet_classifier.pkl"
    
    print(f"Saving trained classifier to {model_path}...")
    with open(model_path, 'wb') as f:
        pickle.dump(clf, f)
        
    print("Training completed successfully!")

if __name__ == "__main__":
    train_classifier()
