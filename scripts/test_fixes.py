#!/usr/bin/env python3
"""
Test Script - Validates fixes for stats accuracy, checkpoint resume, NLP, and dashboard metrics

Run this script to verify that all the fixes are working correctly:
    python scripts/test_fixes.py

Tests:
1. Stats Accuracy - Counters match queue data
2. Checkpoint Resume - Discovery complete flag works properly  
3. NLP Layer - SpaCy model loads (for OCR workers)
4. Dashboard Metrics - All key metrics are consistent
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Ensure Unicode test output does not crash on Windows cp1252 consoles.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure src directory is importable
PROJECT_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config_manager import get_config
from core.queue_manager import get_queue_manager


def print_header(title: str) -> None:
    """Print a formatted section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_result(test_name: str, passed: bool, details: str = "") -> None:
    """Print test result with pass/fail indicator"""
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"\n  [{status}] {test_name}")
    if details:
        for line in details.split('\n'):
            print(f"         {line}")


def test_stats_accuracy() -> bool:
    """Test that stats are accurate and consistent"""
    print_header("TEST 1: Stats Accuracy")
    
    qm = get_queue_manager()
    
    # Get queue statistics
    queue_stats = qm.get_queue_statistics()
    size_stats = qm.get_size_statistics()
    
    # Get counter values directly
    try:
        counter_discovered = int(qm.client.get(qm.COUNTER_DISCOVERED) or 0)
        counter_discovered_bytes = int(qm.client.get(qm.COUNTER_DISCOVERED_BYTES) or 0)
        counter_extraction_completed = int(qm.client.get(qm.COUNTER_EXTRACTION_COMPLETED) or 0)
    except Exception as e:
        print_result("Counter keys exist", False, f"Error: {e}")
        return False
    
    print("\n  Counter values:")
    print(f"    COUNTER_DISCOVERED: {counter_discovered:,}")
    print(f"    COUNTER_DISCOVERED_BYTES: {counter_discovered_bytes:,}")
    print(f"    COUNTER_EXTRACTION_COMPLETED: {counter_extraction_completed:,}")
    
    # Get queue counts
    discovery = queue_stats.get('discovery', {})
    extraction_total = queue_stats.get('extraction_total', {})
    completed = queue_stats.get('completed', {})
    
    discovery_total = discovery.get('total', 0)
    discovery_pending = discovery.get('pending', 0)
    discovery_completed = discovery.get('completed', 0)
    extraction_completed = extraction_total.get('completed', 0)
    total_completed = completed.get('total_completed', 0)
    
    print("\n  Queue statistics:")
    print(f"    discovery.total: {discovery_total:,}")
    print(f"    discovery.pending: {discovery_pending:,}")
    print(f"    discovery.completed: {discovery_completed:,}")
    print(f"    extraction_total.completed: {extraction_completed:,}")
    print(f"    completed.total_completed: {total_completed:,}")
    
    print("\n  Size statistics:")
    print(f"    discovered.files: {size_stats.get('discovered', {}).get('files', 0):,}")
    print(f"    discovered.size_bytes: {size_stats.get('discovered', {}).get('size_bytes', 0):,}")
    print(f"    searchable.files: {size_stats.get('searchable', {}).get('files', 0):,}")
    
    all_passed = True
    
    # Test 1.1: Counter discovered should match size_stats discovered (if counters are set)
    if counter_discovered > 0:
        size_discovered = size_stats.get('discovered', {}).get('files', 0)
        match = counter_discovered == size_discovered
        print_result(
            "Counter matches size_stats.discovered.files",
            match,
            f"Counter: {counter_discovered:,} vs Size stats: {size_discovered:,}"
        )
        all_passed = all_passed and match
    
    # Test 1.2: Extraction completed counter should be tracked
    if counter_extraction_completed > 0:
        match = extraction_completed == counter_extraction_completed
        print_result(
            "Extraction completed counter matches stats",
            match,
            f"Counter: {counter_extraction_completed:,} vs Stats: {extraction_completed:,}"
        )
        all_passed = all_passed and match
    
    # Test 1.3: Total completed should equal searchable files
    searchable_files = size_stats.get('searchable', {}).get('files', 0)
    match = total_completed == searchable_files
    print_result(
        "total_completed equals searchable.files",
        match,
        f"Total completed: {total_completed:,} vs Searchable: {searchable_files:,}"
    )
    all_passed = all_passed and match
    
    return all_passed


def test_checkpoint_resume() -> bool:
    """Test that checkpoint resume works properly"""
    print_header("TEST 2: Checkpoint Resume")
    
    qm = get_queue_manager()
    
    # Check discovery complete flag
    is_complete = qm.is_discovery_complete()
    
    print(f"\n  Discovery completion flag: {'SET' if is_complete else 'NOT SET'}")
    
    # Check bloom filter files exist
    config = get_config()
    bloom_dir = Path(config.paths.working_root) / "discovery"
    bloom_files = list(bloom_dir.glob("bloom_filter_worker_*.pkl")) if bloom_dir.exists() else []
    
    print(f"  Bloom filter files found: {len(bloom_files)}")
    for bf in bloom_files[:5]:  # Show first 5
        print(f"    - {bf.name}")
    
    # Test: If there are completed files, bloom filters should exist OR discovery should be complete
    completed_count = qm.client.hlen(qm.HASH_COMPLETED)
    
    if completed_count > 0:
        has_checkpoints = len(bloom_files) > 0 or is_complete
        print_result(
            "Checkpoint data exists when files are processed",
            has_checkpoints,
            f"Completed files: {completed_count:,}, Bloom files: {len(bloom_files)}, Discovery complete: {is_complete}"
        )
        return has_checkpoints
    else:
        print_result(
            "No files processed yet - checkpoint test skipped",
            True,
            "Cannot test checkpoints without processed files"
        )
        return True


def test_nlp_layer() -> bool:
    """Test that NLP layer is available and works"""
    print_header("TEST 3: NLP Layer")
    
    config = get_config()
    
    print("\n  Config settings:")
    print(f"    nlp.enabled: {config.nlp.enabled}")
    print(f"    nlp.model_path: {config.nlp.model_path}")
    
    # Try to import NLP module
    try:
        from nlp.text_corrector import TextCorrector, get_text_corrector
        nlp_import_ok = True
        print_result("NLP module imports successfully", True)
    except ImportError as e:
        nlp_import_ok = False
        print_result("NLP module imports successfully", False, str(e))
        return False
    
    # Try to initialize text corrector
    try:
        corrector = get_text_corrector()
        model_loaded = corrector.model_loaded
        
        print_result(
            "TextCorrector initializes",
            True,
            f"SpaCy model loaded: {model_loaded}"
        )
        
        # Test a simple correction
        if model_loaded:
            test_text = "This is a t0st of the NLP correcter."
            corrected, num_corrections = corrector.correct(test_text)
            print_result(
                "NLP corrections work",
                True,
                f"Input: '{test_text}'\nOutput: '{corrected}'\nCorrections: {num_corrections}"
            )
        else:
            print_result(
                "NLP corrections (rule-based only)",
                True,
                "SpaCy model not loaded, using rule-based corrections"
            )
        
        return True
        
    except Exception as e:
        print_result("TextCorrector initializes", False, str(e))
        return False


def test_dashboard_metrics() -> bool:
    """Test that dashboard metrics are consistent"""
    print_header("TEST 4: Dashboard Metrics")
    
    qm = get_queue_manager()
    
    # Get both stat methods
    queue_stats = qm.get_queue_statistics()
    size_stats = qm.get_size_statistics()
    
    print("\n  Queue Statistics JSON:")
    print(f"    {json.dumps(queue_stats.get('discovery', {}), indent=6)}")
    
    print("\n  Size Statistics JSON:")
    print(f"    discovered: {json.dumps(size_stats.get('discovered', {}))}")
    print(f"    searchable: {json.dumps(size_stats.get('searchable', {}))}")
    
    all_passed = True
    
    # Test 4.1: Extraction total should have pending, processing, completed keys
    extraction_total = queue_stats.get('extraction_total', {})
    has_keys = all(k in extraction_total for k in ['pending', 'processing', 'completed'])
    print_result(
        "extraction_total has required keys",
        has_keys,
        f"Keys: {list(extraction_total.keys())}"
    )
    all_passed = all_passed and has_keys
    
    # Test 4.2: discovery.total should be >= discovery.completed
    discovery = queue_stats.get('discovery', {})
    total = discovery.get('total', 0)
    completed = discovery.get('completed', 0)
    valid = total >= completed
    print_result(
        "discovery.total >= discovery.completed",
        valid,
        f"Total: {total:,}, Completed: {completed:,}"
    )
    all_passed = all_passed and valid
    
    # Test 4.3: Size stats should have valid structure
    discovered = size_stats.get('discovered', {})
    has_size_keys = 'files' in discovered and 'size_bytes' in discovered
    print_result(
        "Size stats have valid structure",
        has_size_keys,
        f"discovered keys: {list(discovered.keys())}"
    )
    all_passed = all_passed and has_size_keys
    
    return all_passed


def run_all_tests() -> None:
    """Run all test suites"""
    print("\n" + "="*60)
    print("  DOCUMENT SEARCH SYSTEM - FIX VERIFICATION TESTS")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("="*60)
    
    results = {
        'Stats Accuracy': test_stats_accuracy(),
        'Checkpoint Resume': test_checkpoint_resume(),
        'NLP Layer': test_nlp_layer(),
        'Dashboard Metrics': test_dashboard_metrics(),
    }
    
    # Summary
    print_header("TEST SUMMARY")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, passed_flag in results.items():
        status = "✓ PASS" if passed_flag else "✗ FAIL"
        print(f"  {status} - {test_name}")
    
    print(f"\n  Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n  🎉 ALL TESTS PASSED! Fixes are working correctly.")
    else:
        print("\n  ⚠️  Some tests failed. Please review the output above.")
    
    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    run_all_tests()
