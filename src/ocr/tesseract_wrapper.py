"""
Tesseract Wrapper - Integration with Tesseract OCR engine.

Lightweight local alternative to PaddleOCR. Uses far less RAM and CPU,
which makes it the right default for low-memory machines.

Drop-in replacement for PaddleWrapper. The public interface is identical:
    extract_text(image_path) -> Optional[Tuple[str, float]]
    health_check()           -> bool
    get_version()            -> Optional[str]
    get_stats()              -> Dict[str, Any]
    .psm                     (page segmentation mode, honoured per call)
    prewarm()                -> bool

Requires the Tesseract binary on PATH or at the configured path
(Windows: C:\\Program Files\\Tesseract-OCR\\tesseract.exe).
No extra pip packages needed - talks to the binary via subprocess.
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List

from core.logging_manager import get_logger
from core.config_manager import get_config

logger = get_logger("ocr.tesseract")

# Candidate install locations when the binary is not on PATH.
_KNOWN_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    "/usr/bin/tesseract",
    "/usr/local/bin/tesseract",
]


class TesseractWrapper:
    """Wrapper for Tesseract OCR with confidence scoring.

    Text and confidence come from a single TSV-output invocation, so each
    page costs exactly one fast subprocess call.
    """

    def __init__(self):
        self.config = get_config()

        tess_cfg = getattr(self.config.ocr, "tesseract", None)

        self.lang: str = str(getattr(tess_cfg, "lang", "eng") or "eng")
        self.timeout: int = int(getattr(tess_cfg, "timeout_seconds", 60) or 60)

        # PSM attribute - the worker strategy loop sets this per attempt,
        # exactly like it does on PaddleWrapper.
        self.psm: str = str(getattr(tess_cfg, "psm", "3") or "3")
        self._default_psm: str = self.psm

        # Resolve the binary: explicit config path, then PATH, then known spots.
        self.exe: Optional[str] = self._resolve_binary(
            getattr(tess_cfg, "exe_path", "") or ""
        )

        # Statistics (same shape as PaddleWrapper.get_stats)
        self.pages_processed: int = 0
        self.total_confidence: float = 0.0
        self.errors: int = 0

        if self.exe:
            logger.info(f"TesseractWrapper configured - exe={self.exe}, lang={self.lang}")
        else:
            logger.error(
                "Tesseract binary not found. Install it (Windows: "
                "https://github.com/UB-Mannheim/tesseract/releases) or set "
                "ocr.tesseract.exe_path in config."
            )

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------
    def _resolve_binary(self, configured: str) -> Optional[str]:
        if configured and Path(configured).is_file():
            return configured
        on_path = shutil.which("tesseract")
        if on_path:
            return on_path
        for candidate in _KNOWN_PATHS:
            if Path(candidate).is_file():
                return candidate
        return None

    def prewarm(self) -> bool:
        """Verify the binary runs. Called at worker startup."""
        ok = self.health_check()
        if ok:
            logger.info(f"Tesseract pre-warm complete ({self.get_version()}).")
        else:
            logger.warning("Tesseract pre-warm failed.")
        return ok

    # ------------------------------------------------------------------
    # Public API (mirrors PaddleWrapper)
    # ------------------------------------------------------------------
    def extract_text(self, image_path: str) -> Optional[Tuple[str, float]]:
        """Extract text from an image file using Tesseract TSV output.

        Args:
            image_path: Absolute path to the image file.

        Returns:
            (text, confidence_0_to_100) or None on error / no text.
        """
        if not self.exe:
            return None

        try:
            proc = subprocess.run(
                [self.exe, image_path, "stdout", "-l", self.lang,
                 "--psm", str(self.psm), "tsv"],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except FileNotFoundError:
            logger.error(f"Tesseract binary missing at {self.exe}")
            self.exe = self._resolve_binary("")
            self.errors += 1
            return None
        except subprocess.TimeoutExpired:
            logger.warning(f"Tesseract timed out after {self.timeout}s on {image_path}")
            self.errors += 1
            return None
        except Exception as e:
            logger.error(f"Tesseract error on {image_path}: {e}")
            self.errors += 1
            return None

        if proc.returncode != 0:
            logger.warning(
                f"Tesseract exit={proc.returncode} on {Path(image_path).name}: "
                f"{(proc.stderr or '').strip()[:200]}"
            )
            self.errors += 1
            return None

        words: List[str] = []
        confs: List[float] = []
        for line in (proc.stdout or "").splitlines()[1:]:  # skip TSV header
            parts = line.split("\t")
            if len(parts) < 12:
                continue
            try:
                level = int(parts[0])
            except ValueError:
                continue
            if level != 5:  # word-level rows only
                continue
            try:
                conf = float(parts[10])
            except ValueError:
                continue
            text = parts[11].strip()
            if not text:
                continue
            words.append(text)
            if conf >= 0:  # -1 means "no recognised word", skip it
                confs.append(conf)

        if not words:
            return None

        avg_conf = (sum(confs) / len(confs)) if confs else 0.0
        self.pages_processed += 1
        self.total_confidence += avg_conf
        return (" ".join(words), avg_conf)

    def health_check(self) -> bool:
        """Return True if the Tesseract binary runs."""
        if not self.exe:
            return False
        try:
            proc = subprocess.run(
                [self.exe, "--version"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            return proc.returncode == 0
        except Exception:
            return False

    def get_version(self) -> Optional[str]:
        """Return the Tesseract version string."""
        if not self.exe:
            return None
        try:
            proc = subprocess.run(
                [self.exe, "--version"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            first = (proc.stdout or "").splitlines()
            return first[0].strip() if first else None
        except Exception:
            return None

    def get_stats(self) -> Dict[str, Any]:
        """Return processing statistics (same shape as PaddleWrapper.get_stats)."""
        avg_confidence = (
            self.total_confidence / self.pages_processed
            if self.pages_processed > 0
            else 0.0
        )
        return {
            "pages_processed": self.pages_processed,
            "average_confidence": avg_confidence,
            "errors": self.errors,
        }
