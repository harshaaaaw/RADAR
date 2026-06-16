"""
Image Preprocessor - Advanced OpenCV-based preprocessing for better OCR
Based on image_processor.py reference with mode-based and adaptive processing
"""

import cv2
import numpy as np
from PIL import Image
from typing import Optional, Tuple
from enum import Enum
from dataclasses import dataclass
import io

from core.logging_manager import get_logger
from core.config_manager import get_config

logger = get_logger("ocr.preprocessor")


class EnhancementLevel(Enum):
    """Enhancement intensity levels"""
    LIGHT = "light"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"
    EXTREME_RESTORE = "extreme_restore"


@dataclass
class PreprocessingConfig:
    """Configuration for preprocessing"""
    apply_clahe: bool = True
    clahe_clip_limit: float = 2.0
    clahe_grid_size: tuple = (8, 8)
    
    apply_denoise: bool = False
    denoise_strength: int = 10
    
    apply_deskew: bool = False
    
    apply_sharpen: bool = False
    sharpen_amount: float = 1.0
    
    brightness_adjust: float = 0.0


class ImagePreprocessor:
    """
    Advanced image preprocessor for OCR
    
    Features:
    - Mode-based preprocessing (LIGHT, BALANCED, AGGRESSIVE, EXTREME_RESTORE)
    - Dynamic adjustments based on image analysis
    - CLAHE contrast enhancement
    - Gamma correction
    - Denoising
    - Sharpening
    - Skew correction
    - Faded text enhancement
    - Colored background removal
    """
    
    def __init__(self):
        self.config = get_config()
        self.preprocessing_config = self.config.ocr.preprocessing
        
        self.target_dpi = self.preprocessing_config.get('target_dpi', 300)
        self.use_opencv = self.preprocessing_config.get('use_opencv', True)
        self.use_pillow = self.preprocessing_config.get('use_pillow', True)
        
        self._has_opencv_contrib = self._check_opencv_contrib()
        
        logger.info(f"ImagePreprocessor initialized (OpenCV contrib: {self._has_opencv_contrib})")
    
    def _check_opencv_contrib(self) -> bool:
        """Check if OpenCV contrib modules are available"""
        try:
            test_img = np.zeros((10, 10), dtype=np.uint8)
            _ = cv2.ximgproc.createFastBilateralSolverFilter(test_img, 1, 1, 1)
            return True
        except (AttributeError, cv2.error):
            return False
    
    def preprocess(self, image_data: bytes, quality_score: float = None) -> Optional[bytes]:
        """
        Preprocess image for OCR with adaptive enhancement
        
        Args:
            image_data: Raw image bytes
            quality_score: Optional quality score (0-1) for adaptive processing
            
        Returns:
            Preprocessed image bytes or None on error
        """
        try:
            # Check image size to prevent memory issues
            max_raw_size = 50 * 1024 * 1024  # 50MB
            if len(image_data) > max_raw_size:
                logger.warning(f"Image too large ({len(image_data) / 1024 / 1024:.1f}MB), skipping preprocessing")
                return image_data
            
            if self.use_opencv:
                return self._preprocess_opencv_advanced(image_data, quality_score)
            elif self.use_pillow:
                return self._preprocess_pillow(image_data)
            else:
                return image_data
                
        except Exception as e:
            logger.error(f"Error preprocessing image: {e}")
            return None
    
    def _preprocess_opencv_advanced(self, image_data: bytes, quality_score: float = None) -> Optional[bytes]:
        """
        Advanced preprocessing using OpenCV with adaptive enhancements
        """
        try:
            # Convert bytes to numpy array
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                logger.warning("Failed to decode image with OpenCV")
                return image_data
            
            # Check image dimensions - downscale if too large
            max_dimension = 6000
            height, width = img.shape[:2]
            if height > max_dimension or width > max_dimension:
                scale = min(max_dimension / height, max_dimension / width)
                new_width = int(width * scale)
                new_height = int(height * scale)
                logger.info(f"Downscaling large image from {width}x{height} to {new_width}x{new_height}")
                img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)
            
            # Analyze image to determine best processing mode
            brightness, contrast, sharpness = self._analyze_image(img)
            
            # Select enhancement mode based on analysis
            mode = self._select_mode(brightness, contrast, sharpness, quality_score)
            logger.debug(f"Selected preprocessing mode: {mode} (brightness={brightness:.1f}, contrast={contrast:.1f}, sharpness={sharpness:.1f})")
            
            # Get config for mode
            config = self._get_config_for_mode(mode)
            
            # Apply dynamic adjustments
            config = self._adjust_config_dynamic(config, brightness, contrast, sharpness, quality_score)
            gamma = self._select_gamma(brightness)
            
            # Check for special conditions
            has_color = self._detect_colored_regions(img)
            has_faded = self._detect_faded_regions(img)
            
            # Apply preprocessing steps in optimal order
            
            # Step 1: Remove colored backgrounds if detected
            if has_color:
                img = self._remove_color_background(img)
            
            # Step 2: Denoise before other operations
            if config.apply_denoise:
                img = self._apply_denoise(img, config.denoise_strength)
            
            # Step 3: Gamma correction for brightness
            if gamma != 1.0:
                img = self._apply_gamma(img, gamma)
            
            # Step 4: Brightness adjustment
            if config.brightness_adjust != 0:
                img = self._apply_brightness(img, config.brightness_adjust)
            
            # Step 5: CLAHE contrast enhancement
            if config.apply_clahe:
                img = self._apply_clahe(img, config.clahe_clip_limit, config.clahe_grid_size)
            
            # Step 6: Sharpen
            if config.apply_sharpen:
                img = self._apply_sharpen(img, config.sharpen_amount)
            
            # Step 7: Special handling for faded text
            if has_faded:
                img = self._enhance_faded_text(img)
            
            # Step 8: Convert to grayscale for OCR
            if self.preprocessing_config.get('convert_to_grayscale', True):
                if len(img.shape) == 3:
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Step 9: Correct skew
            if self.preprocessing_config.get('correct_skew', True):
                img = self._correct_skew(img)
            
            # Step 10: Binarization (optional, can hurt some images)
            if self.preprocessing_config.get('binarize', False):
                if len(img.shape) == 3:
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                _, img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Encode back to bytes
            _, buffer = cv2.imencode('.png', img)
            return buffer.tobytes()
            
        except Exception as e:
            logger.error(f"Error in OpenCV preprocessing: {e}", exc_info=True)
            return image_data
    
    def _analyze_image(self, img: np.ndarray) -> Tuple[float, float, float]:
        """Analyze image to get brightness, contrast, and sharpness metrics"""
        try:
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img
            
            brightness = float(np.mean(gray))
            contrast = float(np.std(gray))
            sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            
            return brightness, contrast, sharpness
        except Exception as e:
            logger.warning(f"Image analysis failed: {e}")
            return 128.0, 50.0, 200.0  # Default values
    
    def _select_mode(self, brightness: float, contrast: float, sharpness: float, quality_score: float = None) -> str:
        """Select enhancement mode based on image analysis"""
        
        # Use quality score if available
        if quality_score is not None:
            if quality_score < 0.3:
                return "EXTREME_RESTORE"
            elif quality_score < 0.5:
                return "AGGRESSIVE"
            elif quality_score < 0.7:
                return "BALANCED"
            else:
                return "LIGHT"
        
        # Otherwise use image metrics
        # Low contrast images need more enhancement
        if contrast < 25:
            return "EXTREME_RESTORE"
        elif contrast < 40:
            return "AGGRESSIVE"
        
        # Low sharpness images need sharpening
        if sharpness < 80:
            return "AGGRESSIVE"
        elif sharpness < 150:
            return "BALANCED"
        
        # Very dark or very bright images
        if brightness < 60 or brightness > 200:
            return "AGGRESSIVE"
        
        # Normal images
        if brightness < 100 or brightness > 160:
            return "BALANCED"
        
        return "LIGHT"
    
    def _get_config_for_mode(self, mode: str) -> PreprocessingConfig:
        """Get preprocessing config for the given mode"""
        mode = mode.upper()
        
        if mode == "LIGHT":
            return PreprocessingConfig(
                apply_clahe=True,
                clahe_clip_limit=1.5,
                clahe_grid_size=(8, 8),
                apply_denoise=False,
                apply_sharpen=False,
                brightness_adjust=0
            )
        
        elif mode == "BALANCED":
            return PreprocessingConfig(
                apply_clahe=True,
                clahe_clip_limit=2.0,
                clahe_grid_size=(8, 8),
                apply_denoise=True,
                denoise_strength=5,
                apply_sharpen=False,
                brightness_adjust=0
            )
        
        elif mode == "AGGRESSIVE":
            return PreprocessingConfig(
                apply_clahe=True,
                clahe_clip_limit=3.0,
                clahe_grid_size=(4, 4),
                apply_denoise=True,
                denoise_strength=10,
                apply_sharpen=True,
                sharpen_amount=1.2,
                brightness_adjust=10
            )
        
        elif mode == "EXTREME_RESTORE":
            return PreprocessingConfig(
                apply_clahe=True,
                clahe_clip_limit=5.0,
                clahe_grid_size=(4, 4),
                apply_denoise=True,
                denoise_strength=15,
                apply_sharpen=True,
                sharpen_amount=1.5,
                brightness_adjust=20
            )
        
        else:
            logger.warning(f"Unknown mode '{mode}', using BALANCED")
            return self._get_config_for_mode("BALANCED")
    
    def _adjust_config_dynamic(
        self,
        config: PreprocessingConfig,
        brightness: float,
        contrast: float,
        sharpness: float,
        quality_score: Optional[float]
    ) -> PreprocessingConfig:
        """Adjust preprocessing config based on measured image quality"""
        
        # Contrast-driven CLAHE
        if contrast < 25:
            config.apply_clahe = True
            config.clahe_clip_limit = min(5.0, config.clahe_clip_limit + 1.5)
            config.clahe_grid_size = (6, 6)
        elif contrast < 40:
            config.apply_clahe = True
            config.clahe_clip_limit = min(4.0, config.clahe_clip_limit + 0.8)
        else:
            config.clahe_clip_limit = max(1.2, config.clahe_clip_limit - 0.3)
        
        # Sharpness-driven sharpening/denoise balance
        if sharpness < 80:
            config.apply_sharpen = True
            config.sharpen_amount = max(config.sharpen_amount, 1.6)
            config.denoise_strength = min(config.denoise_strength, 6)
        elif sharpness < 150:
            config.apply_sharpen = True
            config.sharpen_amount = max(config.sharpen_amount, 1.3)
        
        # Quality score nudges
        if quality_score is not None and quality_score < 0.50:
            config.apply_denoise = True
            config.denoise_strength = max(config.denoise_strength, 8)
            config.apply_sharpen = True
            config.sharpen_amount = max(config.sharpen_amount, 1.5)
        
        return config
    
    def _select_gamma(self, brightness: float) -> float:
        """Select gamma correction factor based on brightness"""
        if brightness < 80:
            return 0.85  # Brighten dark images
        if brightness > 180:
            return 1.15  # Darken bright images
        return 1.0
    
    def _apply_denoise(self, img: np.ndarray, strength: int) -> np.ndarray:
        """Apply denoising with bilateral filter"""
        try:
            return cv2.bilateralFilter(img, d=9, sigmaColor=strength*5, sigmaSpace=strength*5)
        except Exception as e:
            logger.warning(f"Denoising failed: {e}")
            return img
    
    def _apply_brightness(self, img: np.ndarray, adjust: float) -> np.ndarray:
        """Adjust brightness"""
        try:
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
            hsv[:, :, 2] = np.clip(hsv[:, :, 2] + adjust, 0, 255)
            hsv = hsv.astype(np.uint8)
            return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        except Exception as e:
            logger.warning(f"Brightness adjustment failed: {e}")
            return img
    
    def _apply_clahe(self, img: np.ndarray, clip_limit: float, grid_size: tuple) -> np.ndarray:
        """Apply CLAHE contrast enhancement"""
        try:
            if len(img.shape) == 3:
                lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
                l, a, b = cv2.split(lab)
                clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=grid_size)
                l = clahe.apply(l)
                lab = cv2.merge([l, a, b])
                return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
            else:
                clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=grid_size)
                return clahe.apply(img)
        except Exception as e:
            logger.warning(f"CLAHE failed: {e}")
            return img
    
    def _apply_sharpen(self, img: np.ndarray, amount: float) -> np.ndarray:
        """Apply unsharp masking"""
        try:
            gaussian = cv2.GaussianBlur(img, (0, 0), 2.0)
            sharpened = cv2.addWeighted(img, 1 + amount, gaussian, -amount, 0)
            return np.clip(sharpened, 0, 255).astype(np.uint8)
        except Exception as e:
            logger.warning(f"Sharpening failed: {e}")
            return img
    
    def _apply_gamma(self, img: np.ndarray, gamma: float) -> np.ndarray:
        """Apply gamma correction"""
        try:
            inv_gamma = 1.0 / max(gamma, 0.01)
            table = (np.arange(256) / 255.0) ** inv_gamma * 255.0
            table = table.astype("uint8")
            return cv2.LUT(img, table)
        except Exception as e:
            logger.warning(f"Gamma correction failed: {e}")
            return img
    
    def _detect_faded_regions(self, img: np.ndarray, threshold: float = 0.3) -> bool:
        """Detect if image has faded text regions"""
        try:
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img
            
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
            total_pixels = gray.size
            
            # Count pixels in faded gray range (150-220)
            faded_pixels = np.sum(hist[150:220])
            faded_ratio = faded_pixels / total_pixels
            
            is_faded = (faded_ratio > threshold) or (laplacian_var < 100)
            
            if is_faded:
                logger.debug(f"Faded text detected: faded_ratio={faded_ratio:.2f}, laplacian_var={laplacian_var:.1f}")
            
            return is_faded
            
        except Exception as e:
            logger.warning(f"Faded detection failed: {e}")
            return False
    
    def _detect_colored_regions(self, img: np.ndarray) -> bool:
        """Detect if image has colored regions (like blue table cells)"""
        try:
            if len(img.shape) != 3:
                return False
            
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            saturation = hsv[:, :, 1]
            
            colored_pixels = np.sum(saturation > 30)
            total_pixels = saturation.size
            colored_ratio = colored_pixels / total_pixels
            
            has_color = colored_ratio > 0.05
            
            if has_color:
                logger.debug(f"Colored regions detected: {colored_ratio:.1%} of image")
            
            return has_color
            
        except Exception as e:
            logger.warning(f"Color detection failed: {e}")
            return False
    
    def _remove_color_background(self, img: np.ndarray) -> np.ndarray:
        """Remove colored backgrounds (like blue table cells) to improve OCR"""
        try:
            if len(img.shape) != 3:
                return img
            
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            
            # Define masks for common highlight colors
            blue_lower = np.array([90, 30, 30])
            blue_upper = np.array([130, 255, 255])
            blue_mask = cv2.inRange(hsv, blue_lower, blue_upper)
            
            yellow_lower = np.array([20, 30, 30])
            yellow_upper = np.array([35, 255, 255])
            yellow_mask = cv2.inRange(hsv, yellow_lower, yellow_upper)
            
            green_lower = np.array([35, 30, 30])
            green_upper = np.array([85, 255, 255])
            green_mask = cv2.inRange(hsv, green_lower, green_upper)
            
            combined_mask = cv2.bitwise_or(blue_mask, yellow_mask)
            combined_mask = cv2.bitwise_or(combined_mask, green_mask)
            
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
            dilated_mask = cv2.dilate(combined_mask, kernel, iterations=2)
            
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            clahe = cv2.createCLAHE(clipLimit=5.0, tileGridSize=(4, 4))
            enhanced = clahe.apply(gray)
            
            result = gray.copy()
            result[dilated_mask > 0] = enhanced[dilated_mask > 0]
            
            return cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)
            
        except Exception as e:
            logger.warning(f"Color background removal failed: {e}")
            return img
    
    def _enhance_faded_text(self, img: np.ndarray) -> np.ndarray:
        """Enhanced processing for faded/broken text"""
        try:
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img.copy()
            
            # Aggressive CLAHE
            clahe = cv2.createCLAHE(clipLimit=6.0, tileGridSize=(4, 4))
            enhanced = clahe.apply(gray)
            
            # Bilateral filter
            denoised = cv2.bilateralFilter(enhanced, 9, 75, 75)
            
            # Adaptive thresholding for broken/faded text
            adaptive = cv2.adaptiveThreshold(
                denoised,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                21,
                10
            )
            
            # Morphological close to connect broken text
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            closed = cv2.morphologyEx(adaptive, cv2.MORPH_CLOSE, kernel)
            
            if len(img.shape) == 3:
                return cv2.cvtColor(closed, cv2.COLOR_GRAY2BGR)
            return closed
            
        except Exception as e:
            logger.warning(f"Faded text enhancement failed: {e}")
            return img
    
    def _correct_skew(self, image: np.ndarray) -> np.ndarray:
        """Detect and correct skew in image"""
        try:
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image

            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)
            
            if lines is None:
                return image
            
            angles = []
            for rho, theta in lines[:, 0]:
                angle = np.degrees(theta) - 90
                angles.append(angle)
            
            if not angles:
                return image
            
            median_angle = np.median(angles)
            
            if abs(median_angle) > 0.5:
                (h, w) = image.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
                rotated = cv2.warpAffine(image, M, (w, h),
                                        flags=cv2.INTER_CUBIC,
                                        borderMode=cv2.BORDER_REPLICATE)
                return rotated
            
            return image
            
        except Exception as e:
            logger.warning(f"Skew correction failed: {e}")
            return image
    
    def _preprocess_pillow(self, image_data: bytes) -> Optional[bytes]:
        """Preprocess using PIL/Pillow (simpler fallback)"""
        try:
            img = Image.open(io.BytesIO(image_data))
            
            if self.preprocessing_config.get('convert_to_grayscale', True):
                img = img.convert('L')
            
            if self.preprocessing_config.get('enhance_contrast', True):
                from PIL import ImageEnhance
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(2.0)
            
            output = io.BytesIO()
            img.save(output, format='PNG')
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"Error in Pillow preprocessing: {e}")
            return image_data
