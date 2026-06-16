"""
Indexing Worker - Pulls from indexing queue and bulk indexes to OpenSearch
"""

import time
from typing import List, Dict, Any

from core.logging_manager import get_logger
from core.config_manager import get_config
from core.queue_manager import get_queue_manager
from core.constants import ErrorType

from .opensearch_client import OpenSearchClient
from .document_builder import DocumentBuilder

logger = get_logger("indexing.worker")


class IndexingWorker:
    """Indexing worker - bulk indexes documents to OpenSearch"""
    
    def __init__(self, worker_id: str):
        self.worker_id = worker_id
        
        self.config = get_config()
        self.queue_manager = get_queue_manager()
        
        # Initialize OpenSearch client
        self.os_client = OpenSearchClient()
        self.document_builder = DocumentBuilder()
        self.max_retry_attempts = max(
            5,
            (self.config.indexing.opensearch.max_retries or 0) + 2
        )

        startup_timeout = getattr(
            self.config.indexing.opensearch,
            'startup_timeout_seconds',
            120
        )

        if not self.os_client.wait_for_availability(timeout_seconds=startup_timeout):
            raise RuntimeError(
                f"OpenSearch unavailable after waiting {startup_timeout} seconds"
            )
        
        # Ensure index exists (ignore if already exists)
        if not self.os_client.ensure_index():
            raise RuntimeError("Failed to create/verify OpenSearch index")
        
        # Statistics
        self.documents_indexed = 0
        self.batches_sent = 0
        self.failures = 0
        self.start_time = None
        self.running = False
    
    def run(self) -> None:
        """Main worker loop with timeout-based flushing"""
        self.running = True
        self.start_time = time.time()
        
        logger.info(f"Worker {self.worker_id}: Starting indexing with flush timeout")
        
        consecutive_empty = 0
        max_empty_polls = 10
        
        # Micro-batch accumulation
        current_batch = []
        last_flush_time = time.time()
        batch_start_time = None  # Track when first item was added to batch
        flush_timeout = getattr(self.config.indexing.opensearch, 'flush_timeout_seconds', 10)
        min_batch_wait = 2.0  # Minimum seconds to wait before flushing partial batch
        
        try:
            while self.running:
                # Get batch size from OpenSearch client (adaptive)
                batch_size = self.os_client.current_batch_size
                
                # Claim work from queue
                work_items = self.queue_manager.claim_indexing_work(
                    worker_id=self.worker_id,
                    batch_size=batch_size
                )
                
                if not work_items:
                    # No new work - check if we should flush accumulated batch
                    time_since_batch_start = time.time() - batch_start_time if batch_start_time else 0
                    should_timeout_flush = (
                        current_batch and 
                        time_since_batch_start >= min_batch_wait and
                        (time.time() - last_flush_time) >= flush_timeout
                    )
                    
                    if should_timeout_flush:
                        logger.info(f"Worker {self.worker_id}: Flushing {len(current_batch)} docs (timeout after {time_since_batch_start:.1f}s)")
                        self._process_batch(current_batch)
                        current_batch = []
                        batch_start_time = None
                        last_flush_time = time.time()
                    
                    consecutive_empty += 1
                    
                    if consecutive_empty >= max_empty_polls:
                        logger.debug(f"Worker {self.worker_id}: No work available, idling...")
                        time.sleep(2)
                        consecutive_empty = 0
                    else:
                        time.sleep(0.5)
                    continue
                
                consecutive_empty = 0
                
                # Add to current batch
                current_batch.extend(work_items)
                
                # Track when first item was added to this batch
                if batch_start_time is None:
                    batch_start_time = time.time()
                
                # Check if we should flush (size threshold reached)
                should_flush = len(current_batch) >= batch_size
                
                # Also flush if batch has been accumulating too long
                time_since_batch_start = time.time() - batch_start_time
                if not should_flush and time_since_batch_start >= flush_timeout:
                    should_flush = True
                    logger.debug(f"Worker {self.worker_id}: Batch timeout ({time_since_batch_start:.1f}s)")
                
                if should_flush:
                    self._process_batch(current_batch)
                    current_batch = []
                    batch_start_time = None
                    last_flush_time = time.time()
                
                # Log progress periodically
                if self.batches_sent % 10 == 0 and self.batches_sent > 0:
                    self._log_progress()
            
            # Flush any remaining items on shutdown
            if current_batch:
                logger.info(f"Worker {self.worker_id}: Flushing {len(current_batch)} docs (shutdown)")
                self._process_batch(current_batch)
            
            self._log_final_stats()
            
        except Exception as e:
            logger.error(f"Worker {self.worker_id}: Fatal error: {e}", exc_info=True)
        finally:
            self.running = False
    
    def _process_batch(self, work_items: List[Dict[str, Any]]) -> None:
        """Process a batch of documents for indexing"""
        start_batch_time = time.time()
        
        # Build actions for bulk indexing
        bulk_items = []
        queue_metadata = {}
        # Track extraction times for completion
        file_extraction_times = {}
        
        for work_item in work_items:
            document = self.document_builder.build_document(work_item['document_json'])
            
            if document:
                doc_id = document.get('file_hash') or document.get('content_hash')
                if not doc_id:
                    doc_id = f"file-{work_item['file_id']}"
                doc_id = str(doc_id)
                
                # Track extraction time for this file
                file_extraction_times[work_item['file_id']] = document.get('extraction_time_ms', 0)

                action = {
                    '_index': self.os_client.index_name,
                    '_id': doc_id,
                    '_source': document
                }

                metadata = {
                    'queue_id': work_item['id'],
                    'file_id': work_item['file_id'],
                    'doc_id': doc_id,
                    'retry_count': work_item.get('retry_count', 0)
                }

                queue_metadata[work_item['id']] = metadata
                bulk_items.append({
                    'action': action,
                    'queue_id': metadata['queue_id'],
                    'file_id': metadata['file_id'],
                    'doc_id': metadata['doc_id'],
                    'retry_count': metadata['retry_count']
                })
            else:
                # Document building failed
                logger.error(f"Failed to build document for file_id {work_item['file_id']}")
                self.failures += 1
                
                # Mark as failed
                self.queue_manager.mark_file_failed(
                    file_id=work_item['file_id'],
                    stage='indexing',
                    error_type=ErrorType.INDEXING_ERROR,
                    error_message='Document building failed',
                    file_path=''
                )
        
        if not bulk_items:
            return
        
        # Bulk index to OpenSearch
        result = self.os_client.bulk_index(bulk_items)

        self.batches_sent += 1

        indexed_items = result.get('indexed_items', [])
        failed_items = result.get('failed_items', [])
        transient_error = result.get('transient_error', False)

        if indexed_items:
            indexed_queue_ids = [item['queue_id'] for item in indexed_items if item.get('queue_id')]
            indexed_file_ids = [item['file_id'] for item in indexed_items if item.get('file_id')]
            self.documents_indexed += len(indexed_items)
            
            # Calculate indexing time per document (spread batch time across docs)
            batch_time_ms = int((time.time() - start_batch_time) * 1000)
            per_doc_index_ms = batch_time_ms // max(len(indexed_items), 1)
            
            try:
                if indexed_queue_ids:
                    self.queue_manager.complete_indexing_batch(indexed_queue_ids)
                for file_id in indexed_file_ids:
                    if file_id is not None:
                        extraction_ms = file_extraction_times.get(file_id, 0)
                        self.queue_manager.mark_file_completed(
                            file_id, 
                            extraction_time_ms=extraction_ms,
                            indexing_time_ms=per_doc_index_ms
                        )
            except Exception as exc:
                logger.error(f"Error marking indexed documents complete: {exc}")

        if failed_items:
            transient_queue_ids = []
            permanent_failures = []

            for failure in failed_items:
                queue_id = failure.get('queue_id')
                if queue_id is None:
                    continue

                metadata = queue_metadata.get(queue_id, {})
                retry_count = metadata.get('retry_count', 0)
                file_id = metadata.get('file_id')
                should_retry = failure.get('transient', False) and retry_count < self.max_retry_attempts

                if should_retry:
                    transient_queue_ids.append(queue_id)
                else:
                    permanent_failures.append((queue_id, file_id, failure))

            if transient_queue_ids:
                self.queue_manager.requeue_indexing_items(transient_queue_ids, increment_retry=True)
                logger.warning(
                    "Worker %s: Requeued %s documents for retry (retry counts < %s)",
                    self.worker_id,
                    len(transient_queue_ids),
                    self.max_retry_attempts
                )

            if permanent_failures:
                queue_ids_to_fail = [queue_id for queue_id, _, _ in permanent_failures]
                self.queue_manager.fail_indexing_items(queue_ids_to_fail)

                for queue_id, file_id, failure in permanent_failures:
                    error_message = failure.get('error') or result.get('error', 'Unknown error')
                    if file_id is not None:
                        self.queue_manager.mark_file_failed(
                            file_id=file_id,
                            stage='indexing',
                            error_type=ErrorType.INDEXING_ERROR,
                            error_message=error_message,
                            file_path=''
                        )
                    logger.error(
                        "Worker %s: Permanent indexing failure for queue_id=%s status=%s error=%s",
                        self.worker_id,
                        queue_id,
                        failure.get('status'),
                        error_message
                    )

                self.failures += len(permanent_failures)

        if not indexed_items and transient_error and not failed_items:
            # Entire batch failed transiently – requeue everything if retry budget allows
            queue_ids = [item['queue_id'] for item in bulk_items]
            retryable_ids = []
            for queue_id in queue_ids:
                metadata = queue_metadata.get(queue_id, {})
                if metadata.get('retry_count', 0) < self.max_retry_attempts:
                    retryable_ids.append(queue_id)
                else:
                    file_id = metadata.get('file_id')
                    if file_id is not None:
                        self.queue_manager.fail_indexing_items([queue_id])
                        self.queue_manager.mark_file_failed(
                            file_id=file_id,
                            stage='indexing',
                            error_type=ErrorType.INDEXING_ERROR,
                            error_message=result.get('error', 'OpenSearch connection error'),
                            file_path=''
                        )
                        self.failures += 1

            if retryable_ids:
                self.queue_manager.requeue_indexing_items(retryable_ids, increment_retry=True)
                logger.warning(
                    "Worker %s: Requeued entire batch (%s docs) after transient OpenSearch error",
                    self.worker_id,
                    len(retryable_ids)
                )
                time.sleep(2)
    
    def _log_progress(self) -> None:
        """Log progress statistics with clear formatting"""
        elapsed = time.time() - self.start_time
        rate = self.documents_indexed / elapsed if elapsed > 0 else 0
        
        os_stats = self.os_client.get_stats()
        
        # Get pending count for ETA
        try:
            pending = self.queue_manager.client.llen(self.queue_manager.QUEUE_INDEXING)
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
        
        logger.info(
            f"[{self.worker_id}] "
            f"Indexed: {self.documents_indexed:,} | "
            f"Pending: {pending:,} | "
            f"Fail: {self.failures} | "
            f"Rate: {rate:.0f}/s{eta_str}"
        )
    
    def _log_final_stats(self) -> None:
        """Log final statistics with clear formatting"""
        elapsed = time.time() - self.start_time
        avg_rate = self.documents_indexed / elapsed if elapsed > 0 else 0
        
        os_stats = self.os_client.get_stats()
        
        logger.info(
            f"\n{'='*60}\n"
            f"[{self.worker_id}] Indexing Complete\n"
            f"{'='*60}\n"
            f"  Documents Indexed:  {self.documents_indexed:,}\n"
            f"  Batches Sent:       {self.batches_sent}\n"
            f"  Failures:           {self.failures}\n"
            f"  Total Time:         {elapsed:.1f}s\n"
            f"  Average Rate:       {avg_rate:.0f} docs/sec\n"
            f"  Final Batch Size:   {os_stats['current_batch_size']}\n"
            f"  Avg Batch Time:     {os_stats['average_batch_time_ms']}ms\n"
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
            'running': self.running,
            'documents_indexed': self.documents_indexed,
            'batches_sent': self.batches_sent,
            'failures': self.failures,
            'elapsed_seconds': elapsed,
            'rate_per_second': self.documents_indexed / elapsed if elapsed > 0 else 0
        }
