"""
Enterprise Document Search System - Redis Queue Manager
High-performance queue with Redis for multi-worker concurrency
No more 'database is locked' errors!
"""

import redis
import json
import threading
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from contextlib import contextmanager
import hashlib

from core.config_manager import get_config
from core.constants import (
    QueueStatus, SizeCategory, Priority, ErrorType,
    TABLE_DISCOVERED_FILES, TABLE_EXTRACTION_QUEUE,
    TABLE_INDEXING_QUEUE, TABLE_OCR_QUEUE,
    TABLE_FAILED_FILES, TABLE_COMPLETED_FILES,
    TABLE_FILE_HASHES, TABLE_CONTENT_HASHES
)
from core.logging_manager import get_logger


logger = get_logger("redis_queue_manager")


class RedisQueueManager:
    """
    High-performance queue manager using Redis
    Handles concurrent worker access without locking issues
    
    Uses Redis data structures:
    - Lists for FIFO queues (LPUSH/BRPOP)
    - Sorted Sets for priority queues
    - Hashes for metadata storage
    - Sets for deduplication
    """
    
    # Redis key prefixes
    PREFIX = "docsearch:"
    QUEUE_DISCOVERY = f"{PREFIX}queue:discovery"
    QUEUE_EXTRACTION = f"{PREFIX}queue:extraction"  # Base, extended with size category
    QUEUE_INDEXING = f"{PREFIX}queue:indexing"
    QUEUE_OCR = f"{PREFIX}queue:ocr"
    
    PROCESSING_EXTRACTION = f"{PREFIX}processing:extraction"
    PROCESSING_INDEXING = f"{PREFIX}processing:indexing"
    PROCESSING_OCR = f"{PREFIX}processing:ocr"
    
    # Counter for extraction completed files (not yet indexed)
    COUNTER_EXTRACTION_COMPLETED = f"{PREFIX}counter:extraction_completed"
    # Counter for total discovered files
    COUNTER_DISCOVERED = f"{PREFIX}counter:discovered"
    # Counter for discovered bytes
    COUNTER_DISCOVERED_BYTES = f"{PREFIX}counter:discovered_bytes"
    
    HASH_FILES = f"{PREFIX}files"  # Hash: file_id -> file metadata
    HASH_COMPLETED = f"{PREFIX}completed"  # Hash: file_hash -> completion data
    HASH_FAILED = f"{PREFIX}failed"  # Hash: file_id -> failure data
    
    SET_FILE_HASHES = f"{PREFIX}file_hashes"  # Set of known file hashes
    SET_CONTENT_HASHES = f"{PREFIX}content_hashes"  # Set of known content hashes
    
    COUNTER_FILE_ID = f"{PREFIX}counter:file_id"
    
    def __init__(self, redis_url: str = None):
        """
        Initialize Redis queue manager
        
        Args:
            redis_url: Redis connection URL (default: redis://localhost:6379/0)
        """
        config = get_config()
        
        # Get Redis URL from config or use default
        if redis_url is None:
            redis_config = getattr(config, 'redis', None)
            if redis_config:
                redis_url = getattr(redis_config, 'url', 'redis://localhost:6379/0')
            else:
                redis_url = 'redis://localhost:6379/0'
        
        self.redis_url = redis_url
        
        # Create connection pool for thread safety
        self.pool = redis.ConnectionPool.from_url(
            redis_url,
            max_connections=50,
            decode_responses=True
        )
        
        self._local = threading.local()
        self._lock = threading.RLock()
        
        # Cache for OCR count to avoid slow OpenSearch queries
        self._ocr_count_cache = {'value': 0, 'timestamp': 0, 'ttl': 60}
        
        logger.info(f"Redis queue manager initialized: {redis_url}")
    
    @property
    def client(self) -> redis.Redis:
        """Get thread-local Redis client"""
        if not hasattr(self._local, 'client') or self._local.client is None:
            self._local.client = redis.Redis(connection_pool=self.pool)
        return self._local.client
    
    def reset_database(self) -> None:
        """
        Reset all queues by flushing Redis keys
        WARNING: This deletes all data!
        """
        try:
            # Get all keys with our prefix
            keys = self.client.keys(f"{self.PREFIX}*")
            if keys:
                self.client.delete(*keys)
            logger.info("Redis queues reset complete")
        except Exception as e:
            logger.error(f"Error resetting Redis: {e}")
            raise
    
    def _generate_file_id(self) -> int:
        """Generate unique file ID using Redis INCR"""
        return self.client.incr(self.COUNTER_FILE_ID)
    
    # ========================================================================
    # DISCOVERY OPERATIONS
    # ========================================================================
    
    def add_discovered_file(
        self,
        file_path: str,
        file_name: str,
        file_size: int,
        file_extension: str,
        file_hash: str,
        last_modified: float,
        created: float,
        size_category: SizeCategory,
        priority: Priority
    ) -> Optional[int]:
        """
        Add discovered file to queue
        
        Returns:
            File ID if added, None if duplicate
        """
        try:
            # Check for duplicate using SET
            if self.client.sismember(self.SET_FILE_HASHES, file_hash):
                return None  # Duplicate
            
            # Generate file ID
            file_id = self._generate_file_id()
            
            # Store file metadata
            file_data = {
                'id': file_id,
                'file_path': file_path,
                'file_name': file_name,
                'file_size': file_size,
                'file_extension': file_extension,
                'file_hash': file_hash,
                'last_modified': last_modified,
                'created': created,
                'size_category': size_category.value,
                'priority': priority.value,
                'status': QueueStatus.PENDING.value,
                'discovered_at': datetime.now().timestamp()
            }
            
            # Use pipeline for atomic operations
            pipe = self.client.pipeline()
            pipe.hset(f"{self.HASH_FILES}:{file_id}", mapping=file_data)
            pipe.sadd(self.SET_FILE_HASHES, file_hash)
            pipe.zadd(self.QUEUE_DISCOVERY, {str(file_id): priority.value})
            # Increment discovered counters
            pipe.incr(self.COUNTER_DISCOVERED)
            pipe.incrby(self.COUNTER_DISCOVERED_BYTES, file_size)
            pipe.execute()
            
            return file_id
            
        except Exception as e:
            logger.error(f"Error adding discovered file: {e}")
            return None
    
    def add_discovered_files_batch(self, files: List[Dict[str, Any]]) -> int:
        """
        Add multiple discovered files in batch
        
        Args:
            files: List of file dictionaries
        
        Returns:
            Number of files added
        """
        inserted = 0
        current_time = datetime.now().timestamp()
        
        try:
            pipe = self.client.pipeline()
            
            for file_data in files:
                file_hash = file_data['file_hash']
                
                # Check duplicate (not in pipeline, need immediate result)
                if self.client.sismember(self.SET_FILE_HASHES, file_hash):
                    continue
                
                file_id = self._generate_file_id()
                priority = file_data.get('priority', Priority.NORMAL.value)
                
                metadata = {
                    'id': file_id,
                    'file_path': file_data['file_path'],
                    'file_name': file_data['file_name'],
                    'file_size': file_data['file_size'],
                    'file_extension': file_data.get('file_extension', ''),
                    'file_hash': file_hash,
                    'last_modified': file_data['last_modified'],
                    'created': file_data.get('created', current_time),
                    'size_category': file_data['size_category'],
                    'priority': priority,
                    'status': QueueStatus.PENDING.value,
                    'discovered_at': current_time
                }
                
                pipe.hset(f"{self.HASH_FILES}:{file_id}", mapping=metadata)
                pipe.sadd(self.SET_FILE_HASHES, file_hash)
                pipe.zadd(self.QUEUE_DISCOVERY, {str(file_id): priority})
                inserted += 1
            
            pipe.execute()
            return inserted
            
        except Exception as e:
            logger.error(f"Error in batch add: {e}")
            return inserted
    
    def check_file_hash_exists(self, file_hash: str) -> Optional[Tuple[int, str]]:
        """
        Check if file hash exists in completed files
        
        Returns:
            (file_id, file_path) if exists, None otherwise
        """
        try:
            data = self.client.hget(self.HASH_COMPLETED, file_hash)
            if data:
                info = json.loads(data)
                return (info['file_id'], info['file_path'])
            return None
        except Exception as e:
            logger.error(f"Error checking file hash: {e}")
            return None
    
    # ========================================================================
    # EXTRACTION QUEUE OPERATIONS
    # ========================================================================
    
    def add_to_extraction_queue(
        self,
        file_id: int,
        file_path: str,
        file_size: int,
        size_category: SizeCategory,
        priority: Priority
    ) -> int:
        """Add file to extraction queue"""
        try:
            queue_key = f"{self.QUEUE_EXTRACTION}:{size_category.value}"
            
            item = {
                'id': file_id,  # Use file_id as queue item id
                'file_id': file_id,
                'file_path': file_path,
                'file_size': file_size,
                'size_category': size_category.value,
                'priority': priority.value,
                'status': QueueStatus.PENDING.value,
                'added_at': datetime.now().timestamp()
            }
            
            # Add to priority queue (sorted set)
            self.client.zadd(queue_key, {json.dumps(item): priority.value})
            
            return file_id
            
        except Exception as e:
            logger.error(f"Error adding to extraction queue: {e}")
            return -1
    
    def claim_extraction_work(
        self,
        size_category: SizeCategory,
        worker_id: str,
        batch_size: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Atomically claim work from extraction queue using ZPOPMIN
        
        Priority ordering: Priority 1 (highest) = lowest score, so ZPOPMIN is correct.
        ZPOPMIN returns items with lowest scores first, which are highest priority.
        
        Args:
            size_category: Which queue to pull from
            worker_id: Worker claiming the work
            batch_size: Number of files to claim
        
        Returns:
            List of claimed work items (highest priority first)
        """
        try:
            queue_key = f"{self.QUEUE_EXTRACTION}:{size_category.value}"
            processing_key = f"{self.PROCESSING_EXTRACTION}:{worker_id}"
            
            # ZPOPMIN returns lowest scores first = highest priority (Priority.HIGH=1, Priority.LOW=10)
            items = self.client.zpopmin(queue_key, batch_size)
            
            if not items:
                return []
            
            claimed = []
            current_time = datetime.now().timestamp()
            
            for item_json, score in items:
                item = json.loads(item_json)
                item['claimed_at'] = current_time
                item['worker_id'] = worker_id
                item['status'] = QueueStatus.PROCESSING.value
                
                # Track in processing set with timeout
                self.client.hset(processing_key, str(item['file_id']), json.dumps(item))
                self.client.expire(processing_key, 600)  # 10 minute timeout
                
                claimed.append(item)
            
            return claimed
            
        except Exception as e:
            logger.error(f"Error claiming extraction work: {e}")
            return []
    
    def complete_extraction(self, queue_id: int, processing_time_ms: int) -> None:
        """Mark extraction as complete"""
        try:
            # Remove from all processing sets
            for key in self.client.keys(f"{self.PROCESSING_EXTRACTION}:*"):
                self.client.hdel(key, str(queue_id))
            
            # Update file metadata
            file_key = f"{self.HASH_FILES}:{queue_id}"
            pipe = self.client.pipeline()
            pipe.hset(file_key, 'extraction_time_ms', processing_time_ms)
            pipe.hset(file_key, 'extraction_completed_at', datetime.now().timestamp())
            pipe.hset(file_key, 'status', 'extracted')  # Update status to extracted
            # Increment extraction completed counter
            pipe.incr(self.COUNTER_EXTRACTION_COMPLETED)
            pipe.execute()
            
            logger.debug(f"Completed extraction for file {queue_id} in {processing_time_ms}ms")
            
        except Exception as e:
            logger.error(f"Error completing extraction: {e}")
    
    def get_extraction_queue_size(self, size_category: SizeCategory = None) -> int:
        """Get pending extraction queue size
        
        Args:
            size_category: Specific category to check, or None for all categories
        
        Returns:
            Number of pending files in extraction queue(s)
        """
        try:
            if size_category:
                queue_key = f"{self.QUEUE_EXTRACTION}:{size_category.value}"
                return self.client.zcard(queue_key)
            else:
                # Sum all extraction queues
                total = 0
                for cat in ['tiny', 'small', 'medium', 'large']:
                    queue_key = f"{self.QUEUE_EXTRACTION}:{cat}"
                    total += self.client.zcard(queue_key)
                return total
        except Exception as e:
            logger.error(f"Error getting extraction queue size: {e}")
            return 0
    
    # ========================================================================
    # INDEXING QUEUE OPERATIONS
    # ========================================================================
    
    def add_to_indexing_queue(
        self,
        file_id: int,
        document_json: str
    ) -> int:
        """Add document to indexing queue"""
        try:
            item = {
                'id': file_id,
                'file_id': file_id,
                'document_json': document_json,
                'status': QueueStatus.PENDING.value,
                'added_at': datetime.now().timestamp()
            }
            
            # Use list for FIFO queue (fast LPUSH/BRPOP)
            self.client.lpush(self.QUEUE_INDEXING, json.dumps(item))
            
            return file_id
            
        except Exception as e:
            logger.error(f"Error adding to indexing queue: {e}")
            return -1
    
    def claim_indexing_work(
        self,
        worker_id: str,
        batch_size: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Atomically claim work from indexing queue
        
        Uses LRANGE + LTRIM for batch claiming (atomic with MULTI/EXEC)
        """
        try:
            processing_key = f"{self.PROCESSING_INDEXING}:{worker_id}"
            
            # Use pipeline for atomic batch pop
            pipe = self.client.pipeline()
            pipe.lrange(self.QUEUE_INDEXING, -batch_size, -1)
            pipe.ltrim(self.QUEUE_INDEXING, 0, -(batch_size + 1))
            results = pipe.execute()
            
            items_json = results[0]
            
            if not items_json:
                return []
            
            claimed = []
            current_time = datetime.now().timestamp()
            
            for item_json in items_json:
                item = json.loads(item_json)
                item['claimed_at'] = current_time
                item['worker_id'] = worker_id
                item['status'] = QueueStatus.PROCESSING.value
                
                # Track in processing hash
                self.client.hset(processing_key, str(item['file_id']), item_json)
                self.client.expire(processing_key, 600)  # 10 minute timeout
                
                claimed.append(item)
            
            return claimed
            
        except Exception as e:
            logger.error(f"Error claiming indexing work: {e}")
            return []
    
    def complete_indexing(self, file_ids: List[int]) -> None:
        """Mark indexing as complete for batch of files"""
        try:
            # Remove from all processing sets
            for key in self.client.keys(f"{self.PROCESSING_INDEXING}:*"):
                for file_id in file_ids:
                    self.client.hdel(key, str(file_id))
            
            current_time = datetime.now().timestamp()
            
            # Update file metadata
            pipe = self.client.pipeline()
            for file_id in file_ids:
                file_key = f"{self.HASH_FILES}:{file_id}"
                pipe.hset(file_key, 'indexed_at', current_time)
                pipe.hset(file_key, 'status', QueueStatus.COMPLETED.value)
            pipe.execute()
            
        except Exception as e:
            logger.error(f"Error completing indexing: {e}")
    
    # ========================================================================
    # OCR QUEUE OPERATIONS
    # ========================================================================
    
    def add_to_ocr_queue(
        self,
        file_id: int,
        file_path: str,
        priority: Priority,
        document_id: str = None
    ) -> int:
        """Add file to OCR queue"""
        try:
            item = {
                'id': file_id,
                'file_id': file_id,
                'file_path': file_path,
                'priority': priority.value,
                'document_id': document_id,
                'status': QueueStatus.PENDING.value,
                'added_at': datetime.now().timestamp()
            }
            
            # Priority queue using sorted set
            self.client.zadd(self.QUEUE_OCR, {json.dumps(item): priority.value})
            
            return file_id
            
        except Exception as e:
            logger.error(f"Error adding to OCR queue: {e}")
            return -1
    
    def claim_ocr_work(
        self,
        worker_id: str,
        batch_size: int = 1
    ) -> List[Dict[str, Any]]:
        """Atomically claim work from OCR queue"""
        try:
            processing_key = f"{self.PROCESSING_OCR}:{worker_id}"
            
            # Atomically pop items from sorted set
            items = self.client.zpopmin(self.QUEUE_OCR, batch_size)
            
            if not items:
                return []
            
            claimed = []
            current_time = datetime.now().timestamp()
            
            for item_json, score in items:
                item = json.loads(item_json)
                item['claimed_at'] = current_time
                item['worker_id'] = worker_id
                item['status'] = QueueStatus.PROCESSING.value
                
                self.client.hset(processing_key, str(item['file_id']), json.dumps(item))
                self.client.expire(processing_key, 1800)  # 30 minute timeout for OCR
                
                claimed.append(item)
            
            return claimed
            
        except Exception as e:
            logger.error(f"Error claiming OCR work: {e}")
            return []
    
    def complete_ocr(
        self,
        queue_id: int,
        ocr_confidence: float,
        processing_time_ms: int
    ) -> None:
        """Mark OCR as complete"""
        try:
            # Remove from processing sets
            for key in self.client.keys(f"{self.PROCESSING_OCR}:*"):
                self.client.hdel(key, str(queue_id))
            
            # Update file metadata
            file_key = f"{self.HASH_FILES}:{queue_id}"
            self.client.hset(file_key, mapping={
                'ocr_confidence': ocr_confidence,
                'ocr_time_ms': processing_time_ms,
                'ocr_completed_at': datetime.now().timestamp(),
                'ocr_completed': 1
            })
            
        except Exception as e:
            logger.error(f"Error completing OCR: {e}")
    
    def complete_indexing_batch(self, queue_ids: List[int]) -> None:
        """Mark batch of documents as indexed - remove from indexing processing"""
        try:
            for queue_id in queue_ids:
                # Remove from processing sets
                for key in self.client.keys(f"{self.PROCESSING_INDEXING}:*"):
                    self.client.hdel(key, str(queue_id))
        except Exception as e:
            logger.error(f"Error completing indexing batch: {e}")
    
    def requeue_indexing_items(
        self,
        queue_ids: List[int],
        *,
        increment_retry: bool = True
    ) -> None:
        """Return indexing items to queue for retry"""
        if not queue_ids:
            return
        
        try:
            for queue_id in queue_ids:
                # Find and remove from processing
                for key in self.client.keys(f"{self.PROCESSING_INDEXING}:*"):
                    item_json = self.client.hget(key, str(queue_id))
                    if item_json:
                        self.client.hdel(key, str(queue_id))
                        # Parse and increment retry if needed
                        item = json.loads(item_json)
                        if increment_retry:
                            item['retry_count'] = item.get('retry_count', 0) + 1
                        # Re-add to queue
                        self.client.lpush(self.QUEUE_INDEXING, json.dumps(item))
                        break
        except Exception as e:
            logger.error(f"Error requeuing indexing items: {e}")
    
    def fail_indexing_items(self, queue_ids: List[int]) -> None:
        """Mark indexing items as permanently failed - remove from processing"""
        if not queue_ids:
            return
        
        try:
            failed_count = 0
            for queue_id in queue_ids:
                # Remove from processing sets
                for key in self.client.keys(f"{self.PROCESSING_INDEXING}:*"):
                    item_json = self.client.hget(key, str(queue_id))
                    if item_json:
                        self.client.hdel(key, str(queue_id))
                        # Parse item and mark it failed
                        item = json.loads(item_json)
                        file_id = item.get('file_id')
                        file_path = item.get('file_path', 'unknown')
                        if file_id:
                            # Mark file as failed with all required arguments
                            self.mark_file_failed(
                                file_id=file_id,
                                file_path=file_path,
                                stage='indexing',
                                error_type=ErrorType.INDEXING_ERROR,
                                error_message='Indexing permanently failed'
                            )
                            failed_count += 1
                        break
            if failed_count > 0:
                logger.info(f"Marked {failed_count} indexing items as failed")
        except Exception as e:
            logger.error(f"Error failing indexing items: {e}")
    
    # ========================================================================
    # FILE COMPLETION AND STATISTICS
    # ========================================================================
    
    def mark_file_completed(
        self,
        file_id: int,
        extraction_time_ms: int = 0,
        indexing_time_ms: int = 0,
        # Extended optional args for backward compatibility
        file_path: str = None,
        file_hash: str = None,
        content_hash: str = None,
        document_id: str = None,
        is_duplicate: bool = False,
        duplicate_of: str = None
    ) -> None:
        """Mark a file as fully completed"""
        try:
            file_size = 0
            # Get file info from stored metadata if not provided
            if file_path is None or file_hash is None:
                file_data = self.client.hgetall(f"{self.HASH_FILES}:{file_id}")
                if file_data:
                    file_path = file_path or file_data.get('file_path', '')
                    file_hash = file_hash or file_data.get('file_hash', '')
                    # Get file size from metadata
                    try:
                        file_size = int(file_data.get('file_size', 0))
                    except (ValueError, TypeError):
                        file_size = 0
                else:
                    # Try to find from any file reference
                    file_path = file_path or ''
                    file_hash = file_hash or str(file_id)
            else:
                # Fetch file_size from metadata even when path/hash are provided
                file_data = self.client.hgetall(f"{self.HASH_FILES}:{file_id}")
                if file_data:
                    try:
                        file_size = int(file_data.get('file_size', 0))
                    except (ValueError, TypeError):
                        file_size = 0
            
            completion_data = {
                'file_id': file_id,
                'file_path': file_path,
                'file_hash': file_hash,
                'file_size': file_size,  # Include file_size for size statistics
                'content_hash': content_hash,
                'document_id': document_id or '',
                'is_duplicate': is_duplicate,
                'duplicate_of': duplicate_of,
                'extraction_time_ms': extraction_time_ms,
                'indexing_time_ms': indexing_time_ms,
                'indexed_at': datetime.now().timestamp()
            }
            
            # Store in completed hash
            if file_hash:
                self.client.hset(self.HASH_COMPLETED, file_hash, json.dumps(completion_data))
                # Add file hash to known hashes set
                self.client.sadd(self.SET_FILE_HASHES, file_hash)
            
            # Add content hash to set if present
            if content_hash:
                self.client.sadd(self.SET_CONTENT_HASHES, content_hash)
            
        except Exception as e:
            logger.error(f"Error marking file completed: {e}")
    
    def mark_file_failed(
        self,
        file_id: int,
        file_path: str,
        stage: str,
        error_type: ErrorType,
        error_message: str,
        retry_count: int = 0,
        stack_trace: str = None
    ) -> None:
        """Mark a file as failed"""
        try:
            failure_data = {
                'file_id': file_id,
                'file_path': file_path,
                'stage': stage,
                'error_type': error_type.value if hasattr(error_type, 'value') else str(error_type),
                'error_message': error_message,
                'retry_count': retry_count,
                'stack_trace': stack_trace,
                'failed_at': datetime.now().timestamp()
            }
            
            self.client.hset(self.HASH_FAILED, str(file_id), json.dumps(failure_data))
            
        except Exception as e:
            logger.error(f"Error marking file failed: {e}")
    
    def _get_cached_ocr_count(self, fallback_count: int) -> int:
        """Get OCR completed count with 60-second caching to avoid slow OpenSearch queries"""
        now = time.time()
        cache = self._ocr_count_cache
        
        # Return cached value if still valid
        if now - cache['timestamp'] < cache['ttl']:
            return cache['value']
        
        # Fetch fresh count from OpenSearch
        try:
            from indexing.opensearch_client import OpenSearchClient
            os_client = OpenSearchClient()
            result = os_client.client.search(
                index=os_client.index_name,
                body={"query": {"exists": {"field": "ocr_content"}}, "size": 0},
                request_timeout=3.0
            )
            ocr_completed = result["hits"]["total"]["value"]
            # Update cache
            cache['value'] = ocr_completed
            cache['timestamp'] = now
            return ocr_completed
        except Exception as e:
            logger.debug(f"Error counting OCR completed files: {e}")
            # Use fallback or last cached value
            return cache['value'] if cache['value'] > 0 else fallback_count
    
    def get_queue_stats(self) -> Dict[str, Dict[str, int]]:
        """Get statistics for all queues"""
        try:
            stats = {
                'discovery': {'pending': 0, 'processing': 0, 'completed': 0, 'failed': 0},
                'extraction': {},
                'extraction_total': {'pending': 0, 'processing': 0, 'completed': 0},
                'indexing': {'pending': 0, 'processing': 0, 'completed': 0},
                'ocr': {'pending': 0, 'processing': 0, 'completed': 0}
            }
            
            # Discovery queue
            stats['discovery']['pending'] = self.client.zcard(self.QUEUE_DISCOVERY)
            
            # Get total completed count (all files that finished all required stages)
            total_completed = self.client.hlen(self.HASH_COMPLETED)
            
            # Get extraction completed count from counter (faster and more accurate)
            try:
                extraction_completed = int(self.client.get(self.COUNTER_EXTRACTION_COMPLETED) or 0)
            except (ValueError, TypeError):
                extraction_completed = total_completed  # Fall back to total completed
            
            # Extraction queues by size category
            total_extraction_pending = 0
            total_extraction_processing = 0
            
            # Count processing items across all extraction workers (do this once)
            for key in self.client.keys(f"{self.PROCESSING_EXTRACTION}:*"):
                total_extraction_processing += self.client.hlen(key)
            
            for size_cat in ['tiny', 'small', 'medium', 'large']:
                queue_key = f"{self.QUEUE_EXTRACTION}:{size_cat}"
                pending = self.client.zcard(queue_key)
                total_extraction_pending += pending
                
                stats['extraction'][size_cat] = {
                    'pending': pending,
                    'processing': 0,  # Processing is tracked at total level
                    'completed': 0  # Completed is tracked at total level
                }
            
            # Overall extraction stats - use the counter for accurate completed count
            stats['extraction_total']['pending'] = total_extraction_pending
            stats['extraction_total']['processing'] = total_extraction_processing
            stats['extraction_total']['completed'] = extraction_completed
            
            # Indexing queue
            stats['indexing']['pending'] = self.client.llen(self.QUEUE_INDEXING)
            for key in self.client.keys(f"{self.PROCESSING_INDEXING}:*"):
                stats['indexing']['processing'] += self.client.hlen(key)
            stats['indexing']['completed'] = total_completed  # All completed files went through indexing
            
            # OCR queue - count files that have ocr data
            ocr_completed = 0
            stats['ocr']['pending'] = self.client.zcard(self.QUEUE_OCR)
            for key in self.client.keys(f"{self.PROCESSING_OCR}:*"):
                stats['ocr']['processing'] += self.client.hlen(key)
            
            # Count OCR completed files - use cached value to avoid slow OpenSearch queries
            ocr_completed = self._get_cached_ocr_count(total_completed)
            stats['ocr']['completed'] = ocr_completed
            
            # Completed and failed counts
            stats['discovery']['completed'] = total_completed
            stats['discovery']['failed'] = self.client.hlen(self.HASH_FAILED)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
            return {}
    
    def get_queue_statistics(self) -> Dict[str, Any]:
        """Get comprehensive queue statistics (compatible with SQLite version)"""
        stats = self.get_queue_stats()
        
        # Transform to expected format
        discovery_stats = stats.get('discovery', {})
        extraction_stats = stats.get('extraction', {})
        extraction_total_stats = stats.get('extraction_total', {})
        
        # Get accurate discovered count from counter
        try:
            discovered_total = int(self.client.get(self.COUNTER_DISCOVERED) or 0)
        except (ValueError, TypeError):
            discovered_total = 0
        
        # Fall back to pending + completed if counter not set
        if discovered_total == 0:
            discovered_total = discovery_stats.get('pending', 0) + discovery_stats.get('completed', 0)
        
        return {
            'discovery': {
                'total': discovered_total,
                'pending': discovery_stats.get('pending', 0),
                'processing': discovery_stats.get('processing', 0),
                'completed': discovery_stats.get('completed', 0),
                'failed': discovery_stats.get('failed', 0)
            },
            'extraction': extraction_stats,
            'extraction_total': extraction_total_stats,
            'indexing': stats.get('indexing', {}),
            'ocr': stats.get('ocr', {}),
            'completed': self.get_completed_files_stats(),
            'failures': self._get_failure_breakdown(),
            'total_failures': discovery_stats.get('failed', 0)
        }
    
    def _get_failure_breakdown(self) -> Dict[str, int]:
        """Get failure counts by error type"""
        breakdown = {}
        try:
            cursor = '0'
            while cursor != 0:
                cursor, data = self.client.hscan(self.HASH_FAILED, cursor, count=100)
                for file_id, info_json in data.items():
                    try:
                        info = json.loads(info_json)
                        error_type = info.get('error_type', 'unknown')
                        breakdown[error_type] = breakdown.get(error_type, 0) + 1
                    except:
                        pass
                if cursor == b'0' or cursor == 0:
                    break
        except Exception as e:
            logger.error(f"Error getting failure breakdown: {e}")
        return breakdown
    
    def get_size_statistics(self) -> Dict[str, Any]:
        """Get file size statistics for dashboard display (optimized for Redis)"""
        try:
            # Use counters for discovered stats (much faster than scanning)
            try:
                total_discovered_files = int(self.client.get(self.COUNTER_DISCOVERED) or 0)
                total_discovered_size = int(self.client.get(self.COUNTER_DISCOVERED_BYTES) or 0)
            except (ValueError, TypeError):
                total_discovered_files = 0
                total_discovered_size = 0
            
            # If counters are 0, fall back to scanning (for backwards compatibility)
            if total_discovered_files == 0:
                # Use SCAN to iterate file metadata (more efficient than KEYS)
                cursor = '0'
                while True:
                    cursor, keys = self.client.scan(cursor=cursor, match=f"{self.HASH_FILES}:*", count=500)
                    for key in keys:
                        try:
                            file_size = self.client.hget(key, 'file_size')
                            if file_size:
                                total_discovered_files += 1
                                total_discovered_size += int(file_size)
                        except:
                            pass
                    if cursor == 0 or cursor == b'0':
                        break
            
            # Get completed files count and calculate total indexed size
            completed_files = 0
            completed_size = 0
            cursor = '0'
            while True:
                cursor, data = self.client.hscan(self.HASH_COMPLETED, cursor, count=100)
                for file_hash, info_json in data.items():
                    try:
                        info = json.loads(info_json)
                        completed_files += 1
                        completed_size += info.get('file_size', 0)
                    except:
                        pass
                if cursor == 0 or cursor == b'0':
                    break
            
            # Get failed files count
            failed_files = self.client.hlen(self.HASH_FAILED)
            
            # Calculate in-pipeline count (extraction + indexing + ocr queues)
            in_pipeline = 0
            for size_cat in ['tiny', 'small', 'medium', 'large']:
                in_pipeline += self.client.zcard(f"{self.QUEUE_EXTRACTION}:{size_cat}")
            in_pipeline += self.client.llen(self.QUEUE_INDEXING)
            in_pipeline += self.client.zcard(self.QUEUE_OCR)
            
            # Add processing counts
            for key in self.client.keys(f"{self.PROCESSING_EXTRACTION}:*"):
                in_pipeline += self.client.hlen(key)
            for key in self.client.keys(f"{self.PROCESSING_INDEXING}:*"):
                in_pipeline += self.client.hlen(key)
            for key in self.client.keys(f"{self.PROCESSING_OCR}:*"):
                in_pipeline += self.client.hlen(key)
            
            # Estimate pipeline size (approx from discovered - completed - failed)
            in_pipeline_size = max(0, total_discovered_size - completed_size)
            
            return {
                'discovered': {'files': total_discovered_files, 'size_bytes': total_discovered_size},
                'in_pipeline': {'files': in_pipeline, 'size_bytes': in_pipeline_size},
                'searchable': {'files': completed_files, 'size_bytes': completed_size},
                'failed': {'files': failed_files, 'size_bytes': 0}
            }
        except Exception as e:
            logger.error(f"Error getting size stats: {e}")
            return {
                'discovered': {'files': 0, 'size_bytes': 0},
                'in_pipeline': {'files': 0, 'size_bytes': 0},
                'searchable': {'files': 0, 'size_bytes': 0},
                'failed': {'files': 0, 'size_bytes': 0}
            }
    
    def get_failed_files(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get list of failed files with details"""
        failed = []
        try:
            cursor = '0'
            count = 0
            while cursor != 0 and count < limit:
                cursor, data = self.client.hscan(self.HASH_FAILED, cursor, count=min(100, limit - count))
                for file_id, info_json in data.items():
                    try:
                        info = json.loads(info_json)
                        info['file_id'] = file_id
                        failed.append(info)
                        count += 1
                        if count >= limit:
                            break
                    except:
                        pass
                if cursor == b'0' or cursor == 0:
                    break
        except Exception as e:
            logger.error(f"Error getting failed files: {e}")
        return failed
    
    def get_file_info(self, file_id: int) -> Dict[str, Any]:
        """Get file information by ID"""
        try:
            data = self.client.hgetall(f"{self.HASH_FILES}:{file_id}")
            if data:
                return {k: v for k, v in data.items()}
            return {}
        except Exception as e:
            logger.error(f"Error getting file info: {e}")
            return {}
    
    def get_largest_completed_files(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return the largest completed files"""
        completed = []
        try:
            cursor = '0'
            while cursor != 0:
                cursor, data = self.client.hscan(self.HASH_COMPLETED, cursor, count=100)
                for file_hash, info_json in data.items():
                    try:
                        info = json.loads(info_json)
                        completed.append(info)
                    except:
                        pass
                if cursor == b'0' or cursor == 0:
                    break
            
            # Sort by file size and return top N
            completed.sort(key=lambda x: x.get('file_size', 0), reverse=True)
            return completed[:limit]
        except Exception as e:
            logger.error(f"Error getting largest completed files: {e}")
            return []
    
    def get_ocr_pending_files(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get list of files pending OCR processing"""
        pending = []
        try:
            items = self.client.zrange(self.QUEUE_OCR, 0, limit - 1, withscores=True)
            for item_json, priority in items:
                try:
                    item = json.loads(item_json)
                    item['priority'] = priority
                    item['status'] = 'pending'
                    pending.append(item)
                except:
                    pass
        except Exception as e:
            logger.error(f"Error getting OCR pending files: {e}")
        return pending
    
    def reset_database(self) -> None:
        """Reset all Redis data (WARNING: deletes everything!)"""
        try:
            # Delete all keys with our prefix
            keys = self.client.keys(f"{self.PREFIX}*")
            if keys:
                self.client.delete(*keys)
            logger.info("Redis database reset complete")
        except Exception as e:
            logger.error(f"Error resetting Redis database: {e}")
    
    def get_completed_files_stats(self) -> Dict[str, Any]:
        """Get completion statistics (matches SQLite format for dashboard compatibility)"""
        try:
            total = self.client.hlen(self.HASH_COMPLETED)
            
            # Calculate average times and duplicate count
            total_extract = 0
            total_index = 0
            count = 0
            duplicates = 0
            
            cursor = '0'
            while cursor != 0:
                cursor, data = self.client.hscan(self.HASH_COMPLETED, cursor, count=100)
                for file_hash, info_json in data.items():
                    try:
                        info = json.loads(info_json)
                        total_extract += info.get('extraction_time_ms', 0)
                        total_index += info.get('indexing_time_ms', 0)
                        if info.get('is_duplicate'):
                            duplicates += 1
                        count += 1
                    except:
                        pass
                if cursor == b'0' or cursor == 0:
                    break
            
            avg_extract = total_extract // count if count > 0 else 0
            avg_index = total_index // count if count > 0 else 0
            
            # Return keys matching SQLite QueueManager format for dashboard compatibility
            return {
                'total_completed': total,  # Dashboard expects 'total_completed'
                'total': total,  # Also keep 'total' for backward compatibility
                'duplicates': duplicates,
                'avg_extraction_ms': avg_extract,  # Dashboard expects 'avg_extraction_ms'
                'avg_indexing_ms': avg_index,  # Dashboard expects 'avg_indexing_ms'
            }
            
        except Exception as e:
            logger.error(f"Error getting completed stats: {e}")
            return {
                'total_completed': 0,
                'total': 0,
                'duplicates': 0,
                'avg_extraction_ms': 0,
                'avg_indexing_ms': 0
            }
    
    def reset_stale_processing(self, timeout_minutes: int = 5) -> Dict[str, int]:
        """Reset items that have been stuck in processing state"""
        reset_counts = {'extraction': 0, 'indexing': 0, 'ocr': 0}
        cutoff_time = datetime.now().timestamp() - (timeout_minutes * 60)
        
        try:
            # Check extraction processing
            for key in self.client.keys(f"{self.PROCESSING_EXTRACTION}:*"):
                for file_id, item_json in self.client.hgetall(key).items():
                    item = json.loads(item_json)
                    if item.get('claimed_at', 0) < cutoff_time:
                        # Re-queue
                        queue_key = f"{self.QUEUE_EXTRACTION}:{item.get('size_category', 'medium')}"
                        self.client.zadd(queue_key, {item_json: item.get('priority', 5)})
                        self.client.hdel(key, file_id)
                        reset_counts['extraction'] += 1
            
            # Check indexing processing
            for key in self.client.keys(f"{self.PROCESSING_INDEXING}:*"):
                for file_id, item_json in self.client.hgetall(key).items():
                    item = json.loads(item_json)
                    if item.get('claimed_at', 0) < cutoff_time:
                        self.client.lpush(self.QUEUE_INDEXING, item_json)
                        self.client.hdel(key, file_id)
                        reset_counts['indexing'] += 1
            
            # Check OCR processing
            for key in self.client.keys(f"{self.PROCESSING_OCR}:*"):
                for file_id, item_json in self.client.hgetall(key).items():
                    item = json.loads(item_json)
                    if item.get('claimed_at', 0) < cutoff_time:
                        self.client.zadd(self.QUEUE_OCR, {item_json: item.get('priority', 5)})
                        self.client.hdel(key, file_id)
                        reset_counts['ocr'] += 1
            
        except Exception as e:
            logger.error(f"Error resetting stale items: {e}")
        
        return reset_counts
    
    def get_file_hash_by_id(self, file_id: int) -> Optional[str]:
        """Get file hash for a file ID"""
        try:
            return self.client.hget(f"{self.HASH_FILES}:{file_id}", 'file_hash')
        except Exception as e:
            logger.error(f"Error getting file hash: {e}")
            return None
    
    # ========================================================================
    # DISCOVERY COMPLETION TRACKING (for resume capability)
    # ========================================================================
    
    DISCOVERY_COMPLETED_FLAG = f"{PREFIX}discovery:completed"
    
    def mark_discovery_complete(self) -> None:
        """Mark discovery phase as complete (called when all discovery workers finish)"""
        try:
            self.client.set(self.DISCOVERY_COMPLETED_FLAG, "1", ex=None)
            logger.info("Discovery phase marked as COMPLETE")
        except Exception as e:
            logger.error(f"Error marking discovery complete: {e}")
    
    def is_discovery_complete(self) -> bool:
        """Check if discovery phase has been completed"""
        try:
            return self.client.exists(self.DISCOVERY_COMPLETED_FLAG) == 1
        except Exception as e:
            logger.error(f"Error checking discovery completion: {e}")
            return False
    
    def reset_discovery_completion_flag(self) -> None:
        """Reset discovery completion flag (for starting fresh discovery)"""
        try:
            self.client.delete(self.DISCOVERY_COMPLETED_FLAG)
            logger.info("Discovery completion flag reset")
        except Exception as e:
            logger.error(f"Error resetting discovery flag: {e}")
    
    def is_file_processed(self, file_hash: str) -> bool:
        """Check if a file hash has already been processed"""
        return self.client.sismember(self.SET_FILE_HASHES, file_hash)
    
    def close(self) -> None:
        """Close Redis connections"""
        try:
            self.pool.disconnect()
        except Exception:
            pass


# Singleton instance with thread safety
_redis_queue_manager: Optional[RedisQueueManager] = None
_redis_queue_manager_lock = threading.Lock()


def get_redis_queue_manager() -> RedisQueueManager:
    """Get singleton Redis queue manager instance (thread-safe)"""
    global _redis_queue_manager
    
    if _redis_queue_manager is None:
        with _redis_queue_manager_lock:
            if _redis_queue_manager is None:
                _redis_queue_manager = RedisQueueManager()
    
    return _redis_queue_manager


def reset_redis_queue_manager() -> None:
    """Reset the singleton Redis queue manager instance"""
    global _redis_queue_manager
    
    with _redis_queue_manager_lock:
        if _redis_queue_manager is not None:
            try:
                _redis_queue_manager.close()
            except Exception:
                pass
            _redis_queue_manager = None
