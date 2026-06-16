"""
Comprehensive System Test Script
Tests all phases of the document search pipeline with real data
"""

import sys
import os
import time
import logging

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("system_test")

def test_phase_1_discovery():
    """Phase 1: Test Discovery Worker"""
    logger.info("="*80)
    logger.info("PHASE 1: DISCOVERY WORKER TEST")
    logger.info("="*80)
    
    try:
        from discovery.discovery_worker import DiscoveryWorker
        
        # Initialize worker
        worker = DiscoveryWorker(worker_id="test_discovery")
        
        logger.info(f"Discovery worker initialized: {worker.worker_id}")
        logger.info(f"Bloom filter initialized: {worker.bloom_filter is not None}")
        logger.info(f"Queue manager connected: {worker.queue_manager is not None}")
        
        # Run discovery for limited time
        logger.info("Starting discovery (10 seconds test)...")
        start = time.time()
        
        # Run in background thread
        import threading
        worker.running = True
        thread = threading.Thread(target=worker.run, daemon=True)
        thread.start()
        
        time.sleep(10)
        worker.stop()
        
        elapsed = time.time() - start
        logger.info(f"Discovery test completed in {elapsed:.1f}s")
        
        # Get stats
        stats = worker.queue_manager.get_queue_stats()
        logger.info(f"Queue stats: {stats}")
        
        return True
    except Exception as e:
        logger.error(f"Phase 1 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_phase_2_extraction():
    """Phase 2: Test Extraction Worker"""
    logger.info("="*80)
    logger.info("PHASE 2: EXTRACTION WORKER TEST")
    logger.info("="*80)
    
    try:
        from extraction.extraction_worker import ExtractionWorker
        
        # Initialize worker - get pool_type and tika_port from config
        from core.config_manager import get_config
        config = get_config()
        pool_type = getattr(config.extraction, 'pool_type', 'fast')
        tika_port = int(getattr(config.extraction, 'tika_port', 9998))
        
        worker = ExtractionWorker(
            worker_id="test_extraction", 
            size_category="fast",
            pool_type=pool_type,
            tika_port=tika_port
        )
        
        logger.info(f"Extraction worker initialized: {worker.worker_id}")
        logger.info(f"Size category: {worker.size_category}")
        logger.info(f"Tika available: {worker.tika_client is not None}")
        
        # Check queue
        stats = worker.queue_manager.get_queue_stats()
        extraction_pending = stats.get('extraction_total', {}).get('pending', 0)
        logger.info(f"Extraction queue pending: {extraction_pending}")
        
        return True
    except Exception as e:
        logger.error(f"Phase 2 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_phase_3_ocr():
    """Phase 3: Test OCR Worker"""
    logger.info("="*80)
    logger.info("PHASE 3: OCR WORKER TEST")
    logger.info("="*80)
    
    try:
        from ocr.ocr_worker import OCRWorker
        
        # Initialize worker
        worker = OCRWorker(worker_id="test_ocr")
        
        logger.info(f"OCR worker initialized: {worker.worker_id}")
        logger.info(f"Tesseract available: {worker.tesseract is not None}")
        logger.info(f"Text corrector: {worker.text_corrector}")
        
        # Check queue
        stats = worker.queue_manager.get_queue_stats()
        ocr_pending = stats.get('ocr', {}).get('pending', 0)
        logger.info(f"OCR queue pending: {ocr_pending}")
        
        return True
    except Exception as e:
        logger.error(f"Phase 3 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_phase_4_indexing():
    """Phase 4: Test Indexing Worker"""
    logger.info("="*80)
    logger.info("PHASE 4: INDEXING WORKER TEST")
    logger.info("="*80)
    
    try:
        from indexing.indexing_worker import IndexingWorker
        
        # Initialize worker
        worker = IndexingWorker(worker_id="test_indexing")
        
        logger.info(f"Indexing worker initialized: {worker.worker_id}")
        logger.info(f"OpenSearch client: {worker.os_client is not None}")
        logger.info(f"Document builder: {worker.document_builder is not None}")
        
        return True
    except Exception as e:
        logger.error(f"Phase 4 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_phase_5_tagging():
    """Phase 5: Test Tagging Engine"""
    logger.info("="*80)
    logger.info("PHASE 5: TAGGING ENGINE TEST")
    logger.info("="*80)
    
    try:
        from tagging.tagging_engine import TaggingEngine
        from tagging.tagging_models import TaggingRequest
        
        # Initialize engine
        engine = TaggingEngine()
        
        logger.info(f"Tagging engine initialized")
        logger.info(f"SpaCy available: {engine._spacy_nlp is not None}")
        logger.info(f"Taxonomy loaded: {engine.taxonomy is not None}")
        
        # Test tagging with sample request
        test_req = TaggingRequest(
            file_id=1,
            file_path="C:/test/invoice.pdf",
            file_name="invoice.pdf",
            file_hash="abc123",
            doc_id="doc1",
            file_type="pdf",
            mime_type="application/pdf",
            main_content="Invoice for payment of $500 to ABC Company. Due date is January 15, 2026.",
            ocr_content="",
            embedded_content="",
            metadata={}
        )
        
        result = engine.tag(test_req)
        
        logger.info(f"Tagging result:")
        logger.info(f"  Category: {result.category}")
        logger.info(f"  Department: {result.department}")
        logger.info(f"  Purpose: {result.purpose}")
        logger.info(f"  Confidence: {result.tag_confidence_overall}")
        logger.info(f"  Subtags: {result.dynamic_subtags}")
        logger.info(f"  Status: {result.tagging_status}")
        
        return True
    except Exception as e:
        logger.error(f"Phase 5 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_phase_6_queue_stats():
    """Phase 6: Test Queue Statistics"""
    logger.info("="*80)
    logger.info("PHASE 6: QUEUE STATISTICS TEST")
    logger.info("="*80)
    
    try:
        from core.queue_manager import get_queue_manager
        
        qm = get_queue_manager()
        stats = qm.get_queue_stats()
        
        logger.info("Queue Statistics:")
        for key, value in stats.items():
            logger.info(f"  {key}: {value}")
        
        return True
    except Exception as e:
        logger.error(f"Phase 6 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_phase_7_config():
    """Phase 7: Test Configuration"""
    logger.info("="*80)
    logger.info("PHASE 7: CONFIGURATION TEST")
    logger.info("="*80)
    
    try:
        from core.config_manager import get_config
        
        config = get_config()
        
        logger.info("Configuration:")
        logger.info(f"  Source drive: {config.paths.source_drive}")
        logger.info(f"  Working root: {config.paths.working_root}")
        logger.info(f"  Queue db: {config.paths.queue_db}")
        logger.info(f"  Temp dir: {config.paths.temp_dir}")
        
        # Check source drive exists
        source_path = Path(config.paths.source_drive)
        if source_path.exists():
            file_count = len(list(source_path.iterdir()))
            logger.info(f"  Source files: {file_count}")
        else:
            logger.warning(f"  Source path does not exist!")
        
        return True
    except Exception as e:
        logger.error(f"Phase 7 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all system tests"""
    logger.info("Starting Comprehensive System Tests")
    logger.info("="*80)
    
    results = {}
    
    # Run tests
    results['Config'] = test_phase_7_config()
    results['Queue Stats'] = test_phase_6_queue_stats()
    results['Discovery'] = test_phase_1_discovery()
    results['Extraction'] = test_phase_2_extraction()
    results['OCR'] = test_phase_3_ocr()
    results['Indexing'] = test_phase_4_indexing()
    results['Tagging'] = test_phase_5_tagging()
    
    # Summary
    logger.info("="*80)
    logger.info("TEST SUMMARY")
    logger.info("="*80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "PASSED" if result else "FAILED"
        logger.info(f"  {name}: {status}")
    
    logger.info(f"\nTotal: {passed}/{total} tests passed")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
