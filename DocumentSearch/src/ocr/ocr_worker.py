"""
OCR Worker - Processes images/scanned documents with Tesseract
Includes NLP text correction after OCR
"""

import os
import time
import tempfile
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
import traceback
import shutil

from core.logging_manager import get_logger
from core.config_manager import get_config
from core.queue_manager import get_queue_manager
from core.constants import ErrorType

from .image_preprocessor_advanced import ImagePreprocessor
from .tesseract_wrapper import TesseractWrapper

# Import indexing client for updating documents
import sys
sys.path.append(str(Path(__file__).parent.parent))
from indexing.opensearch_client import OpenSearchClient
from indexing.document_builder import DocumentBuilder

# Try to import PDF support
try:
    from pdf2image import convert_from_path
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

# Try to import NLP corrector
try:
    from nlp.text_corrector import get_text_corrector
    NLP_AVAILABLE = True
except ImportError:
    NLP_AVAILABLE = False

logger = get_logger("ocr.worker")


class OCRWorker:
    """OCR worker - processes scanned documents and images with NLP correction"""
    
    def __init__(self, worker_id: str):
        self.worker_id = worker_id
        
        self.config = get_config()
        self.queue_manager = get_queue_manager()
        
        # Initialize OCR components
        self.preprocessor = ImagePreprocessor()
        self.tesseract = TesseractWrapper()
        
        # Initialize NLP text corrector for OCR text
        self.text_corrector = None
        if NLP_AVAILABLE:
            try:
                self.text_corrector = get_text_corrector()
                logger.info(f"Worker {worker_id}: NLP text corrector initialized for OCR")
            except Exception as e:
                logger.warning(f"Worker {worker_id}: Could not initialize NLP corrector: {e}")
        else:
            logger.warning(f"Worker {worker_id}: NLP module not available for OCR text corrections")

        # Inject Poppler into PATH BEFORE checking availability
        poppler_path = getattr(self.config.ocr, 'poppler_path', '')
        if poppler_path:
            poppler_path = str(poppler_path)
            current_path = os.environ.get("PATH", "")
            if poppler_path not in current_path:
                # Prepend to PATH
                os.environ["PATH"] = poppler_path + os.pathsep + current_path
                logger.info("Worker %s: Injected Poppler into PATH: %s", self.worker_id, poppler_path)
            os.environ.setdefault("POPPLER_PATH", poppler_path)
        
        # NOW check if poppler is available (after PATH injection)
        self.poppler_available = PDF_SUPPORT and self._check_poppler_tools()
        
        # Initialize OpenSearch client for updates
        try:
            self.os_client = OpenSearchClient()
            startup_timeout = getattr(
                self.config.indexing.opensearch,
                'startup_timeout_seconds',
                120
            )

            if not self.os_client.wait_for_availability(timeout_seconds=startup_timeout):
                logger.warning(
                    "Worker %s: OpenSearch unavailable after %ss; OCR updates will be deferred",
                    worker_id,
                    startup_timeout
                )
                self.os_client = None
        except Exception as exc:
            logger.warning(
                "Worker %s: Could not initialize OpenSearch client for OCR updates: %s",
                worker_id,
                exc
            )
            self.os_client = None

        self.document_builder = DocumentBuilder()
        
        # Quality thresholds
        self.quality_config = self.config.ocr.quality
        self.min_confidence = self.quality_config.get('min_confidence', 25)
        self.good_confidence = self.quality_config.get('good_confidence', 70)
        
        # Pending OCR updates for batch processing
        self.pending_updates: List[Dict[str, Any]] = []
        
        # Statistics
        self.files_processed = 0
        self.files_failed = 0
        self.low_confidence_count = 0
        self.total_confidence = 0
        self.nlp_corrections_applied = 0
        self.start_time = None
        self.running = False
        self._poppler_warned = False
    
    def _check_poppler_tools(self) -> bool:
        """Check if poppler tools are available in PATH after injection"""
        tools = ("pdftoppm", "pdfinfo")
        available = all(shutil.which(t) for t in tools)
        
        if not available:
            logger.warning(
                "Worker %s: Poppler tools not found in PATH even after injection. "
                "PDF OCR will be skipped. Verify poppler_path in config.",
                self.worker_id
            )
        else:
            logger.info("Worker %s: Poppler tools detected and ready", self.worker_id)
        
        return available
    
    def run(self) -> None:
        """Main worker loop"""
        self.running = True
        self.start_time = time.time()
        
        logger.info(f"Worker {self.worker_id}: Starting OCR processing")
        
        # Warn if PDF support is not available
        if not PDF_SUPPORT:
            logger.warning(f"Worker {self.worker_id}: PDF support not available - install pdf2image and poppler for PDF OCR")
        elif not self.poppler_available:
            logger.error(
                "Worker %s: Poppler not installed or not in PATH - PDF OCR will be skipped. "
                "Install poppler-utils: Windows users can download from https://github.com/oschwartz10612/poppler-windows/releases/",
                self.worker_id
            )
        
        consecutive_empty = 0
        max_empty_polls = 10
        
        try:
            while self.running:
                # Claim work from OCR queue
                work_items = self.queue_manager.claim_ocr_work(
                    worker_id=self.worker_id,
                    batch_size=1
                )
                
                if not work_items:
                    consecutive_empty += 1
                    
                    if consecutive_empty >= max_empty_polls:
                        logger.debug(f"Worker {self.worker_id}: No work available, idling...")
                        time.sleep(10)
                        consecutive_empty = 0
                    else:
                        time.sleep(2)
                    continue
                
                consecutive_empty = 0
                
                # Process work item
                for work_item in work_items:
                    if not self.running:
                        break
                    
                    self._process_file(work_item)
                    
                    # Log progress periodically
                    if self.files_processed % 50 == 0:
                        self._log_progress()
            
            # Final flush
            if self.pending_updates:
                self._flush_updates()
            
            self._log_final_stats()
            
        except Exception as e:
            logger.error(f"Worker {self.worker_id}: Fatal error: {e}", exc_info=True)
        finally:
            self.running = False
    
    def _process_file(self, work_item: Dict[str, Any]) -> None:
        """Process a single file for OCR with comprehensive error handling"""
        queue_id = work_item['id']
        file_id = work_item['file_id']
        file_path = work_item['file_path']
        
        start_time = time.time()
        
        try:
            # Determine file type and validate
            file_ext = str(file_path).lower().rsplit('.', 1)[-1] if '.' in str(file_path) else ''
            
            # Define supported formats
            image_exts = {'jpg', 'jpeg', 'png', 'tif', 'tiff', 'bmp', 'gif', 'webp'}
            pdf_ext = {'pdf'}
            office_exts = {'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx'}
            
            # Skip office documents - they shouldn't be flagged for OCR
            if file_ext in office_exts:
                logger.warning(f"Skipping Office document (should not be in OCR queue): {file_path}")
                self.queue_manager.complete_ocr(queue_id, 0.0, 0)
                return
            
            # Process based on file type
            if file_ext in image_exts:
                result = self._process_image_file(file_path)
            elif file_ext in pdf_ext:
                result = self._process_pdf_file(file_path)
            else:
                logger.warning(f"Unsupported file type .{file_ext} for OCR: {file_path}")
                self.queue_manager.complete_ocr(queue_id, 0.0, 0)
                return
            
            if not result:
                self._handle_failure(
                    queue_id=queue_id,
                    file_id=file_id,
                    file_path=file_path,
                    error_message="OCR processing returned no result"
                )
                return
            
            ocr_text, confidence = result
            
            # Check confidence threshold - skip very low quality OCR
            if confidence < self.min_confidence:
                self.low_confidence_count += 1
                logger.warning(
                    f"Low confidence OCR ({confidence:.1f}% < {self.min_confidence}%) - skipping indexing for {file_path}"
                )
                # Mark OCR complete but don't update OpenSearch with garbage text
                processing_time_ms = int((time.time() - start_time) * 1000)
                self.queue_manager.complete_ocr(queue_id, confidence, processing_time_ms)
                self.files_processed += 1
                return  # Skip indexing low-quality OCR
            
            # Apply NLP text corrections to OCR text
            if self.text_corrector and ocr_text:
                try:
                    corrected_text, corrections = self.text_corrector.correct(ocr_text)
                    if corrections > 0:
                        ocr_text = corrected_text
                        self.nlp_corrections_applied += corrections
                        logger.debug(f"Applied {corrections} NLP corrections to OCR text for {file_path}")
                except Exception as e:
                    logger.warning(f"NLP correction failed for OCR text {file_path}: {e}")
            
            # Mark OCR complete
            processing_time_ms = int((time.time() - start_time) * 1000)
            self.queue_manager.complete_ocr(queue_id, confidence, processing_time_ms)
            
            # Update document in OpenSearch immediately (partial update)
            file_hash = self._get_file_hash(file_id)
            if not file_hash:
                logger.warning(f"No file hash found for file_id {file_id}, cannot update document")
            elif not self.os_client:
                logger.warning(
                    "Worker %s: OpenSearch client unavailable; OCR update skipped for %s",
                    self.worker_id,
                    file_path
                )
            else:
                doc_id = str(file_hash)
                success = self.os_client.update_document_ocr(doc_id, ocr_text, confidence)
                
                if success:
                    logger.info(f"Worker {self.worker_id}: Updated OCR for {file_path} (confidence={confidence:.1f}%)")
                else:
                    logger.debug(f"OCR update queued for retry: {file_path}")
            
            self.files_processed += 1
            self.total_confidence += confidence
            
        except FileNotFoundError:
            logger.error(f"File not found: {file_path}")
            self._handle_failure(queue_id, file_id, file_path, "File not found")
            
        except PermissionError:
            logger.error(f"Permission denied accessing: {file_path}")
            self._handle_failure(queue_id, file_id, file_path, "Permission denied")
            
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}", exc_info=True)
            error_detail = f"{type(e).__name__}: {str(e)}"
            self._handle_failure(queue_id, file_id, file_path, error_detail)
    
    def _process_image_file(self, file_path: str) -> Optional[Tuple[str, float]]:
        """Process an image file with OCR
        
        Returns:
            Tuple of (text, confidence) or None on failure
        """
        tmp_path = None
        try:
            # Read image file
            with open(file_path, 'rb') as f:
                image_data = f.read()
            
            # Preprocess image
            preprocessed_data = self.preprocessor.preprocess(image_data)
            
            if not preprocessed_data:
                logger.warning(f"Preprocessing failed for {file_path}, using original")
                preprocessed_data = image_data
            
            # Save preprocessed image to temporary file
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.png', delete=False) as tmp_file:
                tmp_file.write(preprocessed_data)
                tmp_path = tmp_file.name
            
            # Run OCR
            result = self.tesseract.extract_text(tmp_path)
            
            if not result:
                logger.warning(f"Tesseract returned no result for {file_path}")
                return None
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing image {file_path}: {e}", exc_info=True)
            return None
            
        finally:
            # Cleanup temp file
            if tmp_path:
                try:
                    Path(tmp_path).unlink()
                except Exception as cleanup_error:
                    logger.debug(f"Failed to cleanup temp file {tmp_path}: {cleanup_error}")
    
    def _process_pdf_file(self, file_path: str) -> Optional[Tuple[str, float]]:
        """Process a PDF file (potentially scanned document) with OCR
        
        Returns:
            Tuple of (text, confidence) or None on failure
        """
        if not PDF_SUPPORT:
            logger.warning(f"PDF support not available (pdf2image not installed), skipping: {file_path}")
            return None

        if not self.poppler_available:
            if not self._poppler_warned:
                logger.error(
                    "Worker %s: Poppler not available in PATH - PDF OCR will be skipped. "
                    "Verify poppler_path in config: %s",
                    self.worker_id,
                    getattr(self.config.ocr, 'poppler_path', 'NOT SET')
                )
                self._poppler_warned = True
            return None
        
        temp_dir = None
        try:
            # Convert PDF to images with explicit poppler path
            try:
                # Pass poppler_path to convert_from_path if configured
                poppler_path = getattr(self.config.ocr, 'poppler_path', None)
                # Use config DPI (default 300 for accuracy)
                # Add thread_count for parallel PDF page conversion
                target_dpi = getattr(self.config.ocr.preprocessing, 'target_dpi', 300)
                if poppler_path:
                    images = convert_from_path(str(file_path), dpi=target_dpi, poppler_path=str(poppler_path), thread_count=4)
                else:
                    images = convert_from_path(str(file_path), dpi=target_dpi, thread_count=4)
            except Exception as pdf_error:
                error_msg = str(pdf_error)
                # Check if it's a poppler issue
                if 'poppler' in error_msg.lower() or 'unable to get page count' in error_msg.lower():
                    self.poppler_available = False
                    if not self._poppler_warned:
                        logger.error(
                            "Worker %s: Poppler tools not found when converting PDF. Error: %s. "
                            "Configured path: %s",
                            self.worker_id,
                            pdf_error,
                            poppler_path or 'NOT SET'
                        )
                        self._poppler_warned = True
                else:
                    logger.error(f"Failed to convert PDF to images: {file_path} - {pdf_error}")
                return None
            
            if not images:
                logger.warning(f"PDF conversion produced no images: {file_path}")
                return None
            
            # Limit max pages to process for performance (OCR is slow)
            max_pages = getattr(self.config.ocr, 'max_pages_per_pdf', 50)
            if len(images) > max_pages:
                logger.info(f"PDF has {len(images)} pages, limiting OCR to first {max_pages} pages: {file_path}")
                images = images[:max_pages]
            
            # Process each page and combine results
            all_text = []
            total_confidence = 0.0
            processed_pages = 0
            
            for page_num, image in enumerate(images, 1):
                try:
                    # Save page as temporary PNG
                    with tempfile.NamedTemporaryFile(mode='wb', suffix='.png', delete=False) as tmp_file:
                        image.save(tmp_file.name, 'PNG')
                        tmp_path = tmp_file.name
                    
                    try:
                        # Run OCR on page
                        result = self.tesseract.extract_text(tmp_path)
                        
                        if result:
                            page_text, page_confidence = result
                            all_text.append(f"\n--- Page {page_num} ---\n{page_text}")
                            total_confidence += page_confidence
                            processed_pages += 1
                        else:
                            logger.warning(f"No OCR result for page {page_num} of {file_path}")
                    
                    finally:
                        # Cleanup page temp file
                        try:
                            Path(tmp_path).unlink()
                        except Exception:
                            pass
                            
                except Exception as page_error:
                    logger.error(f"Error processing page {page_num} of {file_path}: {page_error}")
                    continue
            
            if processed_pages == 0:
                logger.warning(f"No pages successfully processed in PDF: {file_path}")
                return None
            
            # Combine all text and average confidence
            combined_text = "\n".join(all_text)
            avg_confidence = total_confidence / processed_pages
            
            logger.info(f"Successfully processed {processed_pages}/{len(images)} pages of PDF: {file_path}")
            
            return (combined_text, avg_confidence)
            
        except Exception as e:
            logger.error(f"Error processing PDF {file_path}: {e}", exc_info=True)
            return None
    
    def _get_file_hash(self, file_id: int) -> str:
        """Get file hash from database"""
        try:
            file_info = self.queue_manager.get_file_info(file_id)
            return file_info.get('file_hash', '')
        except Exception:
            return ''
    
    def _flush_updates(self) -> None:
        """Flush pending OCR updates to OpenSearch"""
        if not self.pending_updates:
            return
        
        logger.info(f"Worker {self.worker_id}: Flushing {len(self.pending_updates)} OCR updates")
        
        success_count = 0
        for item in self.pending_updates:
            try:
                # Update document in OpenSearch
                # Use file_hash as document ID
                doc_id = item['file_hash']
                
                if not doc_id:
                    logger.warning("Skipping update - no file hash available")
                    continue
                
                success = self.os_client.update_document(doc_id, item['update'])
                
                if success:
                    success_count += 1
                else:
                    logger.debug(f"Document {doc_id} may not exist in index yet")
                    
            except Exception as e:
                error_msg = str(e)
                # Don't log as error if document simply doesn't exist yet
                if 'document_missing' in error_msg or 'NotFoundError' in error_msg:
                    logger.debug(f"Document not yet indexed, will retry later: {item.get('file_id')}")
                else:
                    logger.error(f"Error updating document: {e}")
        
        if success_count > 0:
            logger.info(f"Worker {self.worker_id}: Successfully updated {success_count}/{len(self.pending_updates)} documents")
        
        self.pending_updates = []
    
    def _handle_failure(
        self,
        queue_id: int,
        file_id: int,
        file_path: str,
        error_message: str
    ) -> None:
        """Handle OCR failure"""
        self.files_failed += 1
        
        self.queue_manager.mark_file_failed(
            file_id=file_id,
            stage='ocr',
            error_type=ErrorType.OCR_ERROR,
            error_message=error_message,
            file_path=file_path
        )
        
        # Remove from OCR queue
        try:
            self.queue_manager.complete_ocr(queue_id, 0.0, 0)
        except Exception:
            pass
    
    def _log_progress(self) -> None:
        """Log progress statistics with clear formatting"""
        elapsed = time.time() - self.start_time
        rate = self.files_processed / elapsed if elapsed > 0 else 0
        avg_confidence = self.total_confidence / self.files_processed if self.files_processed > 0 else 0
        
        # Get pending count for ETA
        try:
            pending = self.queue_manager.client.zcard(self.queue_manager.QUEUE_OCR)
        except:
            pending = 0
        
        # Calculate ETA
        eta_str = ""
        if pending > 0 and rate > 0:
            eta_seconds = pending / rate
            if eta_seconds > 3600:
                eta_str = f" | ETA: {eta_seconds/3600:.1f}h"
            elif eta_seconds > 60:
                eta_str = f" | ETA: {eta_seconds/60:.0f}m"
            else:
                eta_str = f" | ETA: {eta_seconds:.0f}s"
        
        nlp_status = "✓NLP" if self.text_corrector else ""
        
        logger.info(
            f"[{self.worker_id}] "
            f"Done: {self.files_processed:,} | "
            f"Pending: {pending:,} | "
            f"Fail: {self.files_failed} | "
            f"Conf: {avg_confidence:.0f}% | "
            f"Rate: {rate:.1f}/s{eta_str} {nlp_status}"
        )
    
    def _log_final_stats(self) -> None:
        """Log final statistics with clear formatting"""
        elapsed = time.time() - self.start_time
        avg_rate = self.files_processed / elapsed if elapsed > 0 else 0
        avg_confidence = self.total_confidence / self.files_processed if self.files_processed > 0 else 0
        
        tesseract_stats = self.tesseract.get_stats()
        nlp_status = "ENABLED" if self.text_corrector else "DISABLED"
        
        logger.info(
            f"\n{'='*60}\n"
            f"[{self.worker_id}] OCR Complete\n"
            f"{'='*60}\n"
            f"  Files Processed:    {self.files_processed:,}\n"
            f"  Files Failed:       {self.files_failed}\n"
            f"  Low Confidence:     {self.low_confidence_count}\n"
            f"  NLP Corrections:    {self.nlp_corrections_applied:,}\n"
            f"  Average Confidence: {avg_confidence:.1f}%\n"
            f"  Total Time:         {elapsed:.1f}s\n"
            f"  Average Rate:       {avg_rate:.1f} files/sec\n"
            f"  Tesseract Pages:    {tesseract_stats['pages_processed']}\n"
            f"  NLP Status:         {nlp_status}\n"
            f"{'='*60}"
        )
    
    def stop(self) -> None:
        """Stop the worker gracefully"""
        logger.info(f"Worker {self.worker_id}: Stop requested")
        self.running = False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics"""
        elapsed = time.time() - self.start_time if self.start_time else 0
        avg_confidence = self.total_confidence / self.files_processed if self.files_processed > 0 else 0
        
        return {
            'worker_id': self.worker_id,
            'running': self.running,
            'files_processed': self.files_processed,
            'files_failed': self.files_failed,
            'low_confidence_count': self.low_confidence_count,
            'average_confidence': avg_confidence,
            'elapsed_seconds': elapsed,
            'rate_per_second': self.files_processed / elapsed if elapsed > 0 else 0
        }
