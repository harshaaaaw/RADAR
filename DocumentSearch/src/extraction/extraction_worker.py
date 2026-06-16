"""
Extraction Worker - Pulls from extraction queue and processes with Tika
Includes NLP text correction before indexing
"""

import gc
import time
import json
from typing import Dict, Any, Optional
from datetime import datetime

from core.logging_manager import get_logger
from core.config_manager import get_config
from core.queue_manager import get_queue_manager
from core.constants import SizeCategory, Priority, ErrorType

from .tika_client import TikaClient
from .content_extractor import ContentExtractor

# Import OpenSearch client for express lane indexing
from indexing.opensearch_client import OpenSearchClient

# Import NLP corrector for text enhancement
try:
    from nlp.text_corrector import get_text_corrector
    NLP_AVAILABLE = True
except ImportError:
    NLP_AVAILABLE = False

logger = get_logger("extraction.worker")


class ExtractionWorker:
    """Extraction worker - processes files with Tika and applies NLP corrections"""
    
    def __init__(self, worker_id: str, pool_type: str, size_category: SizeCategory, tika_port: int):
        self.worker_id = worker_id
        self.pool_type = pool_type
        self.size_category = size_category
        
        self.config = get_config()
        self.queue_manager = get_queue_manager()
        
        # Initialize Tika client
        tika_instance = None
        for instance in self.config.extraction.tika.instances:
            if instance.port == tika_port:
                tika_instance = instance
                break
        
        if not tika_instance:
            raise ValueError(f"No Tika instance configured for port {tika_port}")
        
        self.tika_client = TikaClient(tika_instance.host, tika_instance.port)
        self.content_extractor = ContentExtractor()
        
        # Initialize NLP text corrector only if enabled in config
        self.text_corrector = None
        if self.config.nlp.enabled and NLP_AVAILABLE:
            try:
                self.text_corrector = get_text_corrector()
                logger.info(f"[{worker_id}] NLP text corrector ENABLED and initialized")
            except Exception as e:
                logger.warning(f"[{worker_id}] NLP enabled but failed to initialize: {e}")
        else:
            if not self.config.nlp.enabled:
                # NLP disabled for extraction workers is normal - they process already-clean text
                logger.debug(f"[{worker_id}] NLP disabled (config.nlp.enabled=false)")
            elif not NLP_AVAILABLE:
                logger.warning(f"[{worker_id}] NLP module not available in environment")
        
        # Initialize OpenSearch client for express lane indexing
        try:
            self.os_client = OpenSearchClient()
            startup_timeout = getattr(
                self.config.indexing.opensearch,
                'startup_timeout_seconds',
                120
            )

            if not self.os_client.wait_for_availability(timeout_seconds=startup_timeout):
                logger.warning(
                    "Worker %s: OpenSearch unavailable after %ss; disabling express lane",
                    worker_id,
                    startup_timeout
                )
                self.os_client = None
        except Exception as e:
            logger.warning(f"Worker {worker_id}: Could not initialize OpenSearch client for express lane: {e}")
            self.os_client = None
        
        # Worker configuration - run continuously (no restart threshold)
        # Memory management via periodic garbage collection instead
        self.gc_interval = 100  # Run GC every 100 files
        
        # Statistics
        self.files_processed = 0
        self.nlp_corrections_applied = 0
        self.files_failed = 0
        self.files_with_ocr = 0
        self.total_processing_time = 0
        self.start_time = None
        self.running = False
    
    def run(self) -> None:
        """Main worker loop - runs continuously with memory management"""
        self.running = True
        self.start_time = time.time()
        
        logger.info(f"Worker {self.worker_id} ({self.pool_type}): Starting for {self.size_category.value} files")
        
        consecutive_empty = 0
        max_empty_polls = 10
        
        try:
            while self.running:
                # Periodic garbage collection for memory management
                if self.files_processed > 0 and self.files_processed % self.gc_interval == 0:
                    gc.collect()
                
                # Claim work from queue
                work_items = self.queue_manager.claim_extraction_work(
                    size_category=self.size_category,
                    worker_id=self.worker_id,
                    batch_size=1
                )
                
                if not work_items:
                    consecutive_empty += 1
                    
                    if consecutive_empty >= max_empty_polls:
                        logger.debug(f"Worker {self.worker_id}: No work available, idling...")
                        time.sleep(2)
                        consecutive_empty = 0
                    else:
                        time.sleep(0.5)
                    continue
                
                consecutive_empty = 0
                
                # Process work item
                for work_item in work_items:
                    if not self.running:
                        break
                    
                    self._process_file(work_item)
                    
                    # Log progress periodically
                    if self.files_processed % 100 == 0:
                        self._log_progress()
            
            self._log_final_stats()
            
        except Exception as e:
            logger.error(f"Worker {self.worker_id}: Fatal error: {e}", exc_info=True)
        finally:
            self.running = False
            self.tika_client.close()
    
    def _process_file(self, work_item: Dict[str, Any]) -> None:
        """Process a single file"""
        queue_id = work_item['id']
        file_id = work_item['file_id']
        file_path = work_item['file_path']
        
        start_time = time.time()
        
        try:
            # Extract with Tika
            tika_response = self.tika_client.extract(file_path)
            
            if not tika_response or not tika_response.get('success'):
                # Extraction failed
                self._handle_failure(
                    queue_id=queue_id,
                    file_id=file_id,
                    file_path=file_path,
                    error_type=ErrorType.EXTRACTION_FAILED,
                    error_message="Tika extraction failed or returned no data"
                )
                return
            
            # Process extraction results
            file_hash = self._get_file_hash(file_id)
            
            extracted_data = self.content_extractor.process_tika_response(
                tika_response=tika_response,
                file_path=file_path,
                file_hash=file_hash
            )
            
            if not extracted_data:
                self._handle_failure(
                    queue_id=queue_id,
                    file_id=file_id,
                    file_path=file_path,
                    error_type=ErrorType.EXTRACTION_FAILED,
                    error_message="Content extraction returned no data"
                )
                return
            
            # Mark extraction complete
            processing_time_ms = int((time.time() - start_time) * 1000)
            self.queue_manager.complete_extraction(queue_id, processing_time_ms)
            
            # Build document for indexing
            file_size = work_item.get('file_size', 0)
            document = self._build_document(extracted_data, tika_response, file_size)
            document_json = json.dumps(document)
            
            # Route to express lane or batch indexing
            priority = work_item.get('priority', 5)
            
            # For throughput and fewer OpenSearch refreshes, always use batch queue
            self.queue_manager.add_to_indexing_queue(
                file_id=file_id,
                document_json=document_json
            )
            
            # Queue OCR in parallel (doesn't block indexing)
            if extracted_data.get('needs_ocr', False):
                self.queue_manager.add_to_ocr_queue(
                    file_id=file_id,
                    file_path=file_path,
                    priority=Priority(work_item.get('priority', 5))
                )
                self.files_with_ocr += 1
            
            self.files_processed += 1
            self.total_processing_time += (time.time() - start_time)
            
        except Exception as e:
            logger.error(f"Worker {self.worker_id}: Error processing {file_path}: {e}", exc_info=True)
            self._handle_failure(
                queue_id=queue_id,
                file_id=file_id,
                file_path=file_path,
                error_type=ErrorType.EXTRACTION_ERROR,
                error_message=str(e)
            )
    
    def _get_file_hash(self, file_id: int) -> str:
        """Get file hash from database"""
        try:
            file_info = self.queue_manager.get_file_info(file_id)
            return file_info.get('file_hash', '')
        except Exception:
            return ''
    
    def _build_document(self, extracted_data: Dict[str, Any], tika_response: Dict[str, Any], file_size: int = 0) -> Dict[str, Any]:
        """Build document structure for indexing with NLP text corrections"""
        main_content = extracted_data['main_content']
        nlp_corrections = 0
        
        # Apply NLP text corrections if available
        if self.text_corrector and main_content:
            try:
                corrected_content, corrections = self.text_corrector.correct(main_content)
                if corrections > 0:
                    main_content = corrected_content
                    nlp_corrections = corrections
                    self.nlp_corrections_applied += corrections
                    logger.debug(f"Applied {corrections} NLP corrections to {extracted_data['file_path']}")
            except Exception as e:
                logger.warning(f"NLP correction failed for {extracted_data['file_path']}: {e}")
        
        document = {
            'file_path': extracted_data['file_path'],
            'file_hash': extracted_data['file_hash'],
            'file_size': file_size,  # Include file size for search and display
            'main_content': main_content,  # Use corrected content
            'content_hash': extracted_data['content_hash'],
            'metadata': extracted_data['metadata'],
            'embedded_files': extracted_data['embedded_files'],
            'embedded_count': extracted_data['embedded_count'],
            'needs_ocr': extracted_data['needs_ocr'],
            'extraction_time_ms': tika_response.get('response_time_ms', 0),
            'nlp_corrections': nlp_corrections,
            'extracted_at': datetime.now().isoformat()
        }
        
        return document
    
    def _handle_failure(
        self,
        queue_id: int,
        file_id: int,
        file_path: str,
        error_type: ErrorType,
        error_message: str
    ) -> None:
        """Handle extraction failure"""
        self.files_failed += 1
        
        self.queue_manager.mark_file_failed(
            file_id=file_id,
            stage='extraction',
            error_type=error_type,
            error_message=error_message,
            file_path=file_path
        )
        
        # Remove from extraction queue
        try:
            self.queue_manager.complete_extraction(queue_id, 0)
        except Exception:
            pass
    
    def _log_progress(self) -> None:
        """Log progress statistics with clear formatting"""
        elapsed = time.time() - self.start_time
        rate = self.files_processed / elapsed if elapsed > 0 else 0
        avg_time = self.total_processing_time / self.files_processed if self.files_processed > 0 else 0
        
        # Get queue pending count for ETA calculation
        try:
            pending = self.queue_manager.get_extraction_queue_size(self.size_category)
        except:
            pending = 0
        
        # Calculate ETA if we have pending files and a rate
        eta_str = ""
        if pending > 0 and rate > 0:
            eta_seconds = pending / rate
            if eta_seconds > 3600:
                eta_str = f" | ETA: {eta_seconds/3600:.1f}h"
            elif eta_seconds > 60:
                eta_str = f" | ETA: {eta_seconds/60:.0f}m"
            else:
                eta_str = f" | ETA: {eta_seconds:.0f}s"
        
        logger.info(
            f"[{self.worker_id}] "
            f"Done: {self.files_processed:,} | "
            f"Fail: {self.files_failed} | "
            f"OCR: {self.files_with_ocr} | "
            f"Rate: {rate:.1f}/s | "
            f"Pending: {pending:,}{eta_str}"
        )
    
    def _log_final_stats(self) -> None:
        """Log final statistics with clear formatting"""
        elapsed = time.time() - self.start_time
        avg_rate = self.files_processed / elapsed if elapsed > 0 else 0
        avg_time = self.total_processing_time / self.files_processed if self.files_processed > 0 else 0
        
        tika_stats = self.tika_client.get_stats()
        
        nlp_status = "ENABLED" if self.text_corrector else "DISABLED"
        
        logger.info(
            f"\n{'='*60}\n"
            f"[{self.worker_id}] Extraction Complete ({self.pool_type})\n"
            f"{'='*60}\n"
            f"  Files Processed:    {self.files_processed:,}\n"
            f"  Files Failed:       {self.files_failed}\n"
            f"  Files for OCR:      {self.files_with_ocr}\n"
            f"  Total Time:         {elapsed:.1f}s\n"
            f"  Average Rate:       {avg_rate:.1f} files/sec\n"
            f"  Avg Processing:     {avg_time:.2f}s/file\n"
            f"  Tika Success:       {tika_stats['success_rate']:.1%}\n"
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
        
        return {
            'worker_id': self.worker_id,
            'pool_type': self.pool_type,
            'size_category': self.size_category.value,
            'running': self.running,
            'files_processed': self.files_processed,
            'files_failed': self.files_failed,
            'files_with_ocr': self.files_with_ocr,
            'elapsed_seconds': elapsed,
            'rate_per_second': self.files_processed / elapsed if elapsed > 0 else 0
        }
