import os
import json
from typing import Optional, Tuple
import numpy as np
from pathlib import Path
from PIL import Image
from core.logging_manager import get_logger

logger = get_logger("ocr.visual_memory")

try:
    import torch
    import torchvision.models as models
    import torchvision.transforms as transforms
    _HAS_TORCH = True
except ImportError:
    _HAS_TORCH = False
    logger.warning("PyTorch/Torchvision is not available. VisualMemoryEngine will fall back to perceptual hashing.")


class VisualMemoryEngine:
    """Deep Learning-based Visual Memory Engine.
    Extracts CNN feature vectors from cropped document snippets (signatures, seals, logos)
    and computes cosine similarity against previously approved visual templates.
    """

    def __init__(self):
        self.device = "cuda" if (_HAS_TORCH and torch.cuda.is_available()) else "cpu"
        self.model = None
        self.transform = None

        if _HAS_TORCH:
            try:
                # Use a lightweight MobileNetV3 for lightning fast CPU inference
                self.model = models.mobilenet_v3_small(pretrained=True)
                self.model.eval()  # Freeze weights and activate evaluation mode
                self.model.to(self.device)

                self.transform = transforms.Compose([
                    transforms.Resize((224, 224)),
                    transforms.ToTensor(),
                    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
                ])
                logger.info(f"VisualMemoryEngine: CNN model (MobileNetV3) loaded successfully on {self.device}")
            except Exception as exc:
                logger.error(f"VisualMemoryEngine: Failed to load pre-trained CNN: {exc}")
                self.model = None

    def extract_vector(self, image_path: str) -> Optional[np.ndarray]:
        """Extract a deep learning feature vector from a cropped snippet image."""
        if not _HAS_TORCH or self.model is None:
            return self._extract_fallback_hash(image_path)

        try:
            img = Image.open(image_path).convert('RGB')
            tensor = self.transform(img).unsqueeze(0).to(self.device)
            
            with torch.no_grad():
                # Extract features from the final global average pooling layer
                features = self.model.features(tensor)
                vector = torch.nn.functional.adaptive_avg_pool2d(features, 1).flatten()
                
            # Convert to normalized numpy array
            vector_np = vector.cpu().numpy()
            norm = np.linalg.norm(vector_np)
            if norm > 0:
                vector_np = vector_np / norm
            return vector_np
        except Exception as exc:
            logger.error(f"VisualMemoryEngine: Feature extraction failed for {image_path}: {exc}")
            return None

    def compute_similarity(self, vector_a: np.ndarray, vector_b: np.ndarray) -> float:
        """Compute cosine similarity between two normalized feature vectors."""
        # Vectors are already L2-normalized, so similarity is just their dot product
        return float(np.dot(vector_a, vector_b))

    def match_snippet(self, candidate_image_path: str, approved_vectors_dir: str, threshold: float = 0.88) -> Tuple[bool, Optional[str]]:
        """Compare a candidate snippet against a database of accepted vectors.
        
        Args:
            candidate_image_path: Path to the newly cropped visual snippet.
            approved_vectors_dir: Directory containing accepted numpy vector files (.npy).
            threshold: Cosine similarity threshold for matching (default 0.88).

        Returns:
            (is_match, matched_vector_path)
        """
        candidate_vector = self.extract_vector(candidate_image_path)
        if candidate_vector is None:
            return False, None

        vectors_path = Path(approved_vectors_dir)
        if not vectors_path.exists():
            return False, None

        best_score = -1.0
        best_match_path = None

        # Scan through all accepted .npy vector files
        for f in vectors_path.glob("*.npy"):
            try:
                approved_vector = np.load(str(f))
                score = self.compute_similarity(candidate_vector, approved_vector)
                logger.debug(f"VisualMemoryEngine: Comparing against {f.name} - Similarity: {score:.4f}")
                if score > best_score:
                    best_score = score
                    best_match_path = str(f)
            except Exception as e:
                logger.error(f"VisualMemoryEngine: Error loading approved vector {f.name}: {e}")

        logger.info(f"VisualMemoryEngine: Best match score: {best_score:.4f} (Threshold: {threshold})")
        if best_score >= threshold:
            return True, best_match_path

        return False, None

    def _extract_fallback_hash(self, image_path: str) -> Optional[np.ndarray]:
        """A simple structural/perceptual fallback if PyTorch is missing."""
        try:
            img = Image.open(image_path).convert('L').resize((16, 16), Image.Resampling.LANCZOS)
            pixels = np.array(img, dtype=float)
            # Normalize vector
            flat = pixels.flatten()
            norm = np.linalg.norm(flat)
            if norm > 0:
                flat = flat / norm
            return flat
        except Exception as exc:
            logger.error(f"VisualMemoryEngine: Fallback hashing failed for {image_path}: {exc}")
            return None
