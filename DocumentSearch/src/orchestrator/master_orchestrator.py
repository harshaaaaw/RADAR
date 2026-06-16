"""
Master Orchestrator - Main coordinator for all workers
"""

import time
import multiprocessing as mp
from typing import Dict, List, Any
import signal
import sys

from core.logging_manager import get_logger
from core.config_manager import get_config
from core.queue_manager import get_queue_manager, is_using_redis, try_switch_to_redis
from core.constants import SizeCategory

from discovery.discovery_worker import DiscoveryWorker
from extraction.extraction_worker import ExtractionWorker
from indexing.indexing_worker import IndexingWorker
from ocr.ocr_worker import OCRWorker

from .health_monitor import HealthMonitor
from .resource_monitor import ResourceMonitor
from .checkpoint_manager import CheckpointManager

logger = get_logger("orchestrator")


class MasterOrchestrator:
    """Master orchestrator - spawns and manages all workers"""
    
    def __init__(self):
        self.config = get_config()
        self.queue_manager = get_queue_manager()
        
        # Components
        self.health_monitor = HealthMonitor()
        self.resource_monitor = ResourceMonitor()
        self.checkpoint_manager = CheckpointManager()
        
        # Worker processes
        self.workers: Dict[str, mp.Process] = {}
        self.running = False
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def start(self, mode: str = 'full') -> None:
        """
        Start the system
        
        Args:
            mode: Operation mode (full, resume, incremental)
        """
        self.running = True
        
        logger.info(f"Starting Enterprise Document Search System in {mode} mode")
        logger.info(f"{'=' * 80}")
        
        # Load checkpoint if resuming
        checkpoint_data = None
        if mode == 'resume':
            checkpoint_data = self.checkpoint_manager.load_checkpoint()
        
        # In 'full' mode, reset discovery completion flag to force re-discovery
        if mode == 'full':
            self.queue_manager.reset_discovery_completion_flag()
            logger.info("Full mode: discovery will run again")
        
        # Spawn discovery workers only if discovery is not complete
        if self.queue_manager.is_discovery_complete():
            logger.warning("Discovery already complete, skipping discovery workers - resuming from extraction/indexing")
        else:
            self._spawn_discovery_workers()
        
        # Always spawn extraction, indexing, and OCR workers
        self._spawn_extraction_workers()
        self._spawn_indexing_workers()
        self._spawn_ocr_workers()
        
        logger.info(f"All workers spawned. Total: {len(self.workers)}")
        logger.info(f"{'=' * 80}")
        
        # Start monitoring loops
        try:
            self._main_loop()
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        finally:
            self.stop()
    
    def _spawn_discovery_workers(self) -> None:
        """Spawn discovery workers"""
        # Check if discovery is already complete
        if self.queue_manager.is_discovery_complete():
            logger.info("Discovery already complete (status=COMPLETE), skipping discovery worker spawn")
            return
        
        num_workers = self.config.discovery.num_workers
        
        logger.info(f"Spawning {num_workers} discovery workers...")
        
        for i in range(num_workers):
            worker_id = f"discovery-{i+1}"
            
            process = mp.Process(
                target=self._run_discovery_worker,
                args=(i+1,),
                name=worker_id
            )
            process.start()
            self.workers[worker_id] = process
            
            logger.info(f"  Started {worker_id} (PID: {process.pid})")
    
    def _spawn_extraction_workers(self) -> None:
        """Spawn extraction workers"""
        pools = self.config.extraction.pools
        
        logger.info(f"Spawning extraction workers...")
        
        worker_id_counter = 1
        
        # Fast track workers
        for i in range(pools['fast_track'].num_workers):
            worker_id = f"extraction-fast-{worker_id_counter}"
            process = mp.Process(
                target=self._run_extraction_worker,
                args=(worker_id, 'fast_track', SizeCategory.TINY, pools['fast_track'].tika_ports[0]),
                name=worker_id
            )
            process.start()
            self.workers[worker_id] = process
            logger.info(f"  Started {worker_id} (PID: {process.pid})")
            worker_id_counter += 1
        
        # Standard track workers
        for i in range(pools['standard_track'].num_workers):
            worker_id = f"extraction-std-{worker_id_counter}"
            process = mp.Process(
                target=self._run_extraction_worker,
                args=(worker_id, 'standard_track', SizeCategory.SMALL, pools['standard_track'].tika_ports[0]),
                name=worker_id
            )
            process.start()
            self.workers[worker_id] = process
            logger.info(f"  Started {worker_id} (PID: {process.pid})")
            worker_id_counter += 1
        
        # Heavy track workers
        for i in range(pools['heavy_track'].num_workers):
            worker_id = f"extraction-heavy-{worker_id_counter}"
            process = mp.Process(
                target=self._run_extraction_worker,
                args=(worker_id, 'heavy_track', SizeCategory.MEDIUM, pools['heavy_track'].tika_ports[0]),
                name=worker_id
            )
            process.start()
            self.workers[worker_id] = process
            logger.info(f"  Started {worker_id} (PID: {process.pid})")
            worker_id_counter += 1
        
        # Extreme track workers
        for i in range(pools['extreme_track'].num_workers):
            worker_id = f"extraction-extreme-{worker_id_counter}"
            process = mp.Process(
                target=self._run_extraction_worker,
                args=(worker_id, 'extreme_track', SizeCategory.LARGE, pools['extreme_track'].tika_ports[0]),
                name=worker_id
            )
            process.start()
            self.workers[worker_id] = process
            logger.info(f"  Started {worker_id} (PID: {process.pid})")
            worker_id_counter += 1
    
    def _spawn_indexing_workers(self) -> None:
        """Spawn indexing workers"""
        num_workers = self.config.indexing.num_workers
        
        logger.info(f"Spawning {num_workers} indexing workers...")
        
        for i in range(num_workers):
            worker_id = f"indexing-{i+1}"
            
            process = mp.Process(
                target=self._run_indexing_worker,
                args=(worker_id,),
                name=worker_id
            )
            process.start()
            self.workers[worker_id] = process
            
            logger.info(f"  Started {worker_id} (PID: {process.pid})")
    
    def _spawn_ocr_workers(self) -> None:
        """Spawn OCR workers"""
        num_workers = self.config.ocr.initial_workers
        
        logger.info(f"Spawning {num_workers} OCR workers...")
        
        for i in range(num_workers):
            worker_id = f"ocr-{i+1}"
            
            process = mp.Process(
                target=self._run_ocr_worker,
                args=(worker_id,),
                name=worker_id
            )
            process.start()
            self.workers[worker_id] = process
            
            logger.info(f"  Started {worker_id} (PID: {process.pid})")
    
    @staticmethod
    def _run_discovery_worker(worker_id: int):
        """Run discovery worker in separate process"""
        # Fix Python path for multiprocessing workers
        import sys
        from pathlib import Path
        src_dir = Path(__file__).parent.parent
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))
        
        worker = DiscoveryWorker(worker_id)
        worker.run()
    
    @staticmethod
    def _run_extraction_worker(worker_id: str, pool_type: str, size_category: SizeCategory, tika_port: int):
        """Run extraction worker in separate process"""
        # Fix Python path for multiprocessing workers
        import sys
        from pathlib import Path
        src_dir = Path(__file__).parent.parent
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))
        
        worker = ExtractionWorker(worker_id, pool_type, size_category, tika_port)
        worker.run()
    
    @staticmethod
    def _run_indexing_worker(worker_id: str):
        """Run indexing worker in separate process"""
        # Fix Python path for multiprocessing workers
        import sys
        from pathlib import Path
        src_dir = Path(__file__).parent.parent
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))
        
        worker = IndexingWorker(worker_id)
        worker.run()
    
    @staticmethod
    def _run_ocr_worker(worker_id: str):
        """Run OCR worker in separate process"""
        # Fix Python path for multiprocessing workers
        import sys
        from pathlib import Path
        src_dir = Path(__file__).parent.parent
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))
        
        worker = OCRWorker(worker_id)
        worker.run()
    
    def _main_loop(self) -> None:
        """Main monitoring loop"""
        checkpoint_interval = self.config.orchestrator.checkpoint['interval_seconds']
        last_checkpoint = time.time()
        last_stale_cleanup = time.time()
        last_redis_check = time.time()
        stale_cleanup_interval = 120  # Check for stale items every 2 minutes
        redis_check_interval = 60  # Check for Redis availability every 60 seconds
        
        while self.running:
            try:
                # Check worker health and respawn dead workers
                self._check_workers()
                
                # Monitor system resources
                resources = self.resource_monitor.check_resources()
                
                if resources.get('critical', False):
                    logger.error("CRITICAL: System resources exhausted!")
                    # Could trigger throttling or graceful shutdown here
                
                # Try to switch to Redis if currently using SQLite fallback
                if not is_using_redis() and (time.time() - last_redis_check) >= redis_check_interval:
                    if try_switch_to_redis():
                        logger.info("Successfully migrated from SQLite to Redis backend")
                        # Update queue_manager reference
                        self.queue_manager = get_queue_manager()
                    last_redis_check = time.time()
                
                # Periodic cleanup of stale processing items
                if time.time() - last_stale_cleanup >= stale_cleanup_interval:
                    try:
                        reset_counts = self.queue_manager.reset_stale_processing(timeout_minutes=5)
                        if any(reset_counts.values()):
                            logger.info(f"Reset stale items: {reset_counts}")
                    except Exception as e:
                        logger.warning(f"Stale cleanup failed: {e}")
                    last_stale_cleanup = time.time()
                
                # Create checkpoint
                if time.time() - last_checkpoint >= checkpoint_interval:
                    self.checkpoint_manager.create_checkpoint()
                    last_checkpoint = time.time()
                
                # Check if work is complete
                stats = self.queue_manager.get_queue_stats()
                if self._is_work_complete(stats):
                    logger.info("All queues empty - work complete!")
                    # Could start OCR workers here if not already started
                    # self._spawn_ocr_workers()
                
                time.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(5)
    
    def _check_workers(self) -> None:
        """Check health of worker processes and respawn dead ones"""
        for worker_id, process in list(self.workers.items()):
            if not process.is_alive():
                exit_code = process.exitcode
                logger.warning(f"Worker {worker_id} (PID: {process.pid}) has died (exit code: {exit_code})")
                
                # Remove from tracking
                del self.workers[worker_id]
                
                # Auto-respawn the worker
                self._respawn_worker(worker_id)
    
    def _respawn_worker(self, worker_id: str) -> None:
        """Respawn a dead worker based on its ID"""
        try:
            if worker_id.startswith('discovery-'):
                # Parse worker number from ID like "discovery-1"
                worker_num = int(worker_id.split('-')[1])
                process = mp.Process(
                    target=self._run_discovery_worker,
                    args=(worker_num,),
                    name=worker_id
                )
                process.start()
                self.workers[worker_id] = process
                logger.info(f"Respawned {worker_id} (PID: {process.pid})")
                
            elif worker_id.startswith('extraction-fast-'):
                pools = self.config.extraction.pools
                process = mp.Process(
                    target=self._run_extraction_worker,
                    args=(worker_id, 'fast_track', SizeCategory.TINY, pools['fast_track'].tika_ports[0]),
                    name=worker_id
                )
                process.start()
                self.workers[worker_id] = process
                logger.info(f"Respawned {worker_id} (PID: {process.pid})")
                
            elif worker_id.startswith('extraction-std-'):
                pools = self.config.extraction.pools
                process = mp.Process(
                    target=self._run_extraction_worker,
                    args=(worker_id, 'standard_track', SizeCategory.SMALL, pools['standard_track'].tika_ports[0]),
                    name=worker_id
                )
                process.start()
                self.workers[worker_id] = process
                logger.info(f"Respawned {worker_id} (PID: {process.pid})")
                
            elif worker_id.startswith('extraction-heavy-'):
                pools = self.config.extraction.pools
                process = mp.Process(
                    target=self._run_extraction_worker,
                    args=(worker_id, 'heavy_track', SizeCategory.MEDIUM, pools['heavy_track'].tika_ports[0]),
                    name=worker_id
                )
                process.start()
                self.workers[worker_id] = process
                logger.info(f"Respawned {worker_id} (PID: {process.pid})")
                
            elif worker_id.startswith('extraction-extreme-'):
                pools = self.config.extraction.pools
                process = mp.Process(
                    target=self._run_extraction_worker,
                    args=(worker_id, 'extreme_track', SizeCategory.LARGE, pools['extreme_track'].tika_ports[0]),
                    name=worker_id
                )
                process.start()
                self.workers[worker_id] = process
                logger.info(f"Respawned {worker_id} (PID: {process.pid})")
                
            elif worker_id.startswith('indexing-'):
                process = mp.Process(
                    target=self._run_indexing_worker,
                    args=(worker_id,),
                    name=worker_id
                )
                process.start()
                self.workers[worker_id] = process
                logger.info(f"Respawned {worker_id} (PID: {process.pid})")
                
            elif worker_id.startswith('ocr-'):
                process = mp.Process(
                    target=self._run_ocr_worker,
                    args=(worker_id,),
                    name=worker_id
                )
                process.start()
                self.workers[worker_id] = process
                logger.info(f"Respawned {worker_id} (PID: {process.pid})")
                
        except Exception as e:
            logger.error(f"Failed to respawn worker {worker_id}: {e}")
    
    def _is_work_complete(self, stats: Dict[str, Any]) -> bool:
        """Check if all work is complete"""
        # Work is complete if extraction and indexing queues are empty
        # Keys from get_queue_stats() are: 'extraction_total', 'indexing', etc.
        extraction_pending = stats.get('extraction_total', {}).get('pending', 0)
        extraction_processing = stats.get('extraction_total', {}).get('processing', 0)
        indexing_pending = stats.get('indexing', {}).get('pending', 0)
        indexing_processing = stats.get('indexing', {}).get('processing', 0)
        
        # Work is complete when no items are pending or processing
        return (extraction_pending == 0 and extraction_processing == 0 and 
                indexing_pending == 0 and indexing_processing == 0)
    
    def stop(self) -> None:
        """Stop all workers gracefully"""
        if not self.running:
            return
        
        self.running = False
        
        logger.info("Stopping all workers...")
        logger.info(f"{'=' * 80}")
        
        # Create final checkpoint
        self.checkpoint_manager.create_checkpoint()
        
        # Terminate all worker processes
        for worker_id, process in self.workers.items():
            logger.info(f"Stopping {worker_id}...")
            process.terminate()
        
        # Wait for processes to finish
        grace_period = self.config.orchestrator.shutdown['grace_period_seconds']
        start_time = time.time()
        
        while time.time() - start_time < grace_period:
            alive = [w for w in self.workers.values() if w.is_alive()]
            if not alive:
                break
            time.sleep(1)
        
        # Force kill any remaining processes
        for process in self.workers.values():
            if process.is_alive():
                logger.warning(f"Force killing process {process.pid}")
                process.kill()
        
        logger.info("All workers stopped")
        logger.info(f"{'=' * 80}")
    
    def _signal_handler(self, signum, frame):
        """Handle termination signals"""
        logger.info(f"Received signal {signum}")
        self.running = False
