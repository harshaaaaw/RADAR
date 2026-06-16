"""
Discovery Worker - Orchestrates file scanning, hashing, and queue insertion
"""

import time
import signal
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

from core.logging_manager import get_logger
from core.config_manager import get_config
from core.queue_manager import get_queue_manager
from core.constants import SizeCategory, Priority
from utils.bloom_filter import BloomFilter

from .file_scanner import FileScanner
from .hash_calculator import HashCalculator

logger = get_logger("discovery.worker")


class DiscoveryWorker:
    """Discovery worker process - scans filesystem and populates queues"""
    
    def __init__(self, worker_id: int):
        self.worker_id = worker_id
        self.config = get_config()
        self.queue_manager = get_queue_manager()
        
        # Initialize components
        self.scanner = FileScanner()
        self.hash_calculator = HashCalculator()
        
        # Bloom filter persistence path
        self.bloom_filter_path = Path(self.config.paths.working_root) / "discovery" / f"bloom_filter_worker_{worker_id}.pkl"
        self.bloom_filter_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load or initialize Bloom filter
        self.bloom_filter = self._initialize_bloom_filter()
        
        # Statistics
        self.files_discovered = 0
        self.files_duplicate = 0
        self.files_queued = 0
        self.start_time = None
        self.running = False
        
        # Batch configuration
        self.batch_size = self.config.discovery.batch_size
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _initialize_bloom_filter(self) -> BloomFilter:
        """Initialize Bloom filter from saved file, database, or create new one"""
        bloom_config = self.config.deduplication['bloom_filter']
        
        # Try to load from disk first (fastest)
        if self.bloom_filter_path.exists():
            try:
                logger.info(f"Worker {self.worker_id}: Loading Bloom filter from {self.bloom_filter_path}")
                bloom = BloomFilter.load_from_file(str(self.bloom_filter_path))
                logger.info(f"Worker {self.worker_id}: Loaded Bloom filter with {bloom.elements_added:,} elements")
                return bloom
            except Exception as e:
                logger.warning(f"Worker {self.worker_id}: Failed to load Bloom filter: {e}. Creating new one.")
        
        # Create new Bloom filter
        bloom = BloomFilter(
            expected_elements=bloom_config['expected_elements'],
            false_positive_rate=bloom_config['false_positive_rate']
        )
        
        # Populate from database
        logger.info(f"Worker {self.worker_id}: Populating Bloom filter from database...")
        count = bloom.populate_from_database(self.queue_manager)
        logger.info(f"Worker {self.worker_id}: Loaded {count:,} hashes into Bloom filter")
        
        return bloom
    
    def run(self) -> None:
        """Main worker loop"""
        self.running = True
        self.start_time = time.time()
        last_log_time = time.time()
        
        # Check if discovery is already complete - if so, exit immediately
        if self.queue_manager.is_discovery_complete():
            logger.info(f"Worker {self.worker_id}: Discovery already marked COMPLETE, exiting")
            self._log_final_stats()
            return
        
        source_drive = self.config.paths.source_drive
        logger.info(f"Worker {self.worker_id}: Starting discovery on {source_drive}")
        
        batch = []
        
        try:
            for file_metadata in self.scanner.scan(source_drive):
                if not self.running:
                    break
                
                # Periodic heartbeat (every 30 seconds even if no new files)
                if time.time() - last_log_time > 30:
                    self._log_progress()
                    last_log_time = time.time()
                
                # Calculate file hash
                file_hash = self.hash_calculator.calculate_hash(file_metadata['file_path'])
                if not file_hash:
                    continue
                
                file_metadata['file_hash'] = file_hash
                self.files_discovered += 1
                
                # Log progress periodically (every 10 files)
                if self.files_discovered % 10 == 0:
                    self._log_progress()
                
                # Check for duplicates using Bloom filter
                if self.bloom_filter.contains(file_hash):
                    # Potential duplicate - skip
                    self.files_duplicate += 1
                    continue
                
                # Not a duplicate - add to Bloom filter and queue for processing
                self.bloom_filter.add(file_hash)
                batch.append(file_metadata)
                
                # Process batch when full
                if len(batch) >= self.batch_size:
                    self._process_batch(batch)
                    batch = []
            
            # Process remaining files
            if batch:
                self._process_batch(batch)
            
            self._log_final_stats()
            
        except KeyboardInterrupt:
            logger.info(f"Worker {self.worker_id}: Interrupted by user")
        except Exception as e:
            logger.error(f"Worker {self.worker_id}: Fatal error: {e}", exc_info=True)
        finally:
            self._save_bloom_filter()
            self.running = False
            logger.info(f"Worker {self.worker_id}: Shutdown complete")
    
    def _process_batch(self, batch: list) -> None:
        """Process a batch of discovered files"""
        for file_metadata in batch:
            try:
                # Add to discovered_files table
                file_id = self.queue_manager.add_discovered_file(
                    file_path=file_metadata['file_path'],
                    file_name=file_metadata['file_name'],
                    file_size=file_metadata['file_size'],
                    file_extension=file_metadata['extension'],
                    file_hash=file_metadata['file_hash'],
                    last_modified=file_metadata['modified_time'],
                    created=file_metadata['created_time'],
                    size_category=self._categorize_file_size(file_metadata['file_size']),
                    priority=Priority(file_metadata['priority'])
                )
                
                # Skip if duplicate (file_id is None)
                if file_id is None:
                    self.files_duplicate += 1
                    continue
                
                # Determine size category for routing
                size_category = self._categorize_file_size(file_metadata['file_size'])
                
                # Add to extraction queue
                self.queue_manager.add_to_extraction_queue(
                    file_id=file_id,
                    file_path=file_metadata['file_path'],
                    file_size=file_metadata['file_size'],
                    size_category=size_category,
                    priority=Priority(file_metadata['priority'])
                )
                
                self.files_queued += 1
                
            except Exception as e:
                logger.error(f"Worker {self.worker_id}: Error processing file "
                           f"{file_metadata['file_path']}: {e}")
    
    def _categorize_file_size(self, size: int) -> SizeCategory:
        """Categorize file by size for worker routing"""
        thresholds = self.config.discovery.size_categories
        
        if size < thresholds['tiny']:
            return SizeCategory.TINY
        elif size < thresholds['small']:
            return SizeCategory.SMALL
        elif size < thresholds['medium']:
            return SizeCategory.MEDIUM
        else:
            return SizeCategory.LARGE
    
    def _log_progress(self) -> None:
        """Log progress statistics with clear formatting"""
        elapsed = time.time() - self.start_time
        rate = self.files_discovered / elapsed if elapsed > 0 else 0
        new_files = self.files_queued
        
        # Calculate percentage of files that are new vs already indexed
        total_found = self.files_discovered
        pct_new = (self.files_queued / total_found * 100) if total_found > 0 else 0
        pct_dup = (self.files_duplicate / total_found * 100) if total_found > 0 else 0
        
        logger.info(
            f"[Discovery-{self.worker_id}] "
            f"Scanned: {self.files_discovered:,} ({rate:.0f}/s) | "
            f"New: {new_files:,} ({pct_new:.0f}%) | "
            f"Skip: {self.files_duplicate:,} ({pct_dup:.0f}%)"
        )
    
    def _log_final_stats(self) -> None:
        """Log final statistics and mark discovery complete"""
        elapsed = time.time() - self.start_time
        avg_rate = self.files_discovered / elapsed if elapsed > 0 else 0
        
        scanner_stats = self.scanner.get_stats()
        hash_stats = self.hash_calculator.get_stats()

        # Guard against BloomFilter implementations without __len__ to avoid fatal TypeError
        try:
            bloom_elements = len(self.bloom_filter)
        except Exception:
            bloom_elements = getattr(self.bloom_filter, "elements_added", 0)
        
        logger.info(
            f"\n{'='*60}\n"
            f"Worker {self.worker_id} - Discovery Complete\n"
            f"{'='*60}\n"
            f"  Files Scanned:           {scanner_stats['files_scanned']:,}\n"
            f"  Files Skipped:           {scanner_stats['files_skipped']:,}\n"
            f"  Files Discovered:        {self.files_discovered:,}\n"
            f"  Already Indexed:         {self.files_duplicate:,}\n"
            f"  New Files Queued:        {self.files_queued:,}\n"
            f"  Hash Errors:             {hash_stats['errors']}\n"
            f"  Total Time:              {elapsed:.1f}s\n"
            f"  Average Rate:            {avg_rate:.0f} files/sec\n"
            f"  Bloom Filter Elements:   {bloom_elements:,}\n"
            f"{'='*60}"
        )
        
        # Mark discovery complete when any worker finishes the full scan
        # This enables better checkpoint/resume behavior
        logger.info(f"Worker {self.worker_id}: Marking discovery as complete")
        self.queue_manager.mark_discovery_complete()
    
    def _signal_handler(self, signum, frame) -> None:
        """Handle shutdown signals gracefully"""
        logger.info(f"Worker {self.worker_id}: Received signal {signum}, shutting down gracefully...")
        self.stop()
    
    def _save_bloom_filter(self) -> None:
        """Save Bloom filter to disk for resume"""
        try:
            logger.info(f"Worker {self.worker_id}: Saving Bloom filter to {self.bloom_filter_path}")
            self.bloom_filter.save_to_file(str(self.bloom_filter_path))
            logger.info(f"Worker {self.worker_id}: Bloom filter saved ({self.bloom_filter.elements_added:,} elements)")
        except Exception as e:
            logger.error(f"Worker {self.worker_id}: Failed to save Bloom filter: {e}")
    
    def stop(self) -> None:
        """Stop the worker gracefully"""
        logger.info(f"Worker {self.worker_id}: Stop requested")
        self.running = False
        self._save_bloom_filter()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics"""
        elapsed = time.time() - self.start_time if self.start_time else 0
        
        return {
            'worker_id': self.worker_id,
            'running': self.running,
            'files_discovered': self.files_discovered,
            'files_duplicate': self.files_duplicate,
            'files_queued': self.files_queued,
            'elapsed_seconds': elapsed,
            'rate_per_second': self.files_discovered / elapsed if elapsed > 0 else 0
        }
