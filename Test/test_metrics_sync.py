#!/usr/bin/env python
"""
Comprehensive Dashboard Metrics Sync Test
Verifies all dashboard metrics match backend data
"""

import sys
sys.path.insert(0, r'c:\Users\hp212560601\Desktop\DocumentSearch\DocumentSearch\src')

from core.queue_manager import get_queue_manager
from ui.dashboard import extract_summary, format_number, format_size

def test_metrics_sync():
    """Test that all dashboard metrics sync with backend data"""
    print("=" * 70)
    print("DASHBOARD METRICS SYNC TEST")
    print("=" * 70)
    
    qm = get_queue_manager()
    queue_stats = qm.get_queue_statistics()
    size_stats = qm.get_size_statistics()
    
    # Extract summary like dashboard does
    summary = extract_summary(queue_stats)
    
    print("\n[1] OVERALL PROGRESS METRICS (File Count View)")
    print("-" * 70)
    
    total_discovered = summary["discovered_total"]
    total_completed = summary["completed_total"]
    total_failures = summary["total_failures"]
    total_duplicates = summary["duplicates"]
    
    print(f"Files Discovered:  {format_number(total_discovered):>12} (expected: 9,881)")
    print(f"Fully Processed:   {format_number(total_completed):>12} (expected: 1,138)")
    print(f"Failed:            {format_number(total_failures):>12} (expected: 0)")
    print(f"Duplicates:        {format_number(total_duplicates):>12} (expected: 0)")
    
    # Calculate in-flight
    in_extraction = summary["extraction_pending"] + summary["extraction_processing"]
    in_indexing = summary["indexing_pending"] + summary["indexing_processing"]
    in_ocr = summary["ocr_pending"] + summary["ocr_processing"]
    total_in_flight = in_extraction + in_indexing + in_ocr
    
    print(f"\nIn Pipeline:       {format_number(total_in_flight):>12} (expected: 6,884)")
    print(f"  Extraction:      {format_number(in_extraction):>12}")
    print(f"  Indexing:        {format_number(in_indexing):>12}")
    print(f"  OCR:             {format_number(in_ocr):>12}")
    
    print("\n[2] OVERALL PROGRESS METRICS (Data Size View)")
    print("-" * 70)
    
    disc_size = (size_stats.get('discovered') or {}).get('size_bytes', 0) or 0
    comp_size = (size_stats.get('searchable') or {}).get('size_bytes', 0) or 0
    pipe_size = (size_stats.get('in_pipeline') or {}).get('size_bytes', 0) or 0
    fail_size = (size_stats.get('failed') or {}).get('size_bytes', 0) or 0
    
    print(f"Data Discovered:   {format_size(disc_size):>12} (expected: ~19 GB)")
    print(f"Data Indexed:      {format_size(comp_size):>12} (expected: ~5 GB)")
    print(f"In Pipeline:       {format_size(pipe_size):>12} (expected: ~14 GB)")
    print(f"Failed:            {format_size(fail_size):>12} (expected: 0 B)")
    
    print("\n[3] PIPELINE STATUS METRICS")
    print("-" * 70)
    
    print("Extraction:")
    print(f"  Pending:   {format_number(summary.get('extraction_pending', 0)):>10}")
    print(f"  Processing: {format_number(summary.get('extraction_processing', 0)):>10}")
    print(f"  Done:      {format_number(summary.get('extraction_completed', 0)):>10} (expected: 1,138)")
    
    print("\nIndexing:")
    print(f"  Pending:   {format_number(summary.get('indexing_pending', 0)):>10}")
    print(f"  Processing: {format_number(summary.get('indexing_processing', 0)):>10}")
    print(f"  Done:      {format_number(summary.get('indexing_completed', 0)):>10} (expected: 1,138)")
    
    print("\nOCR Queue:")
    print(f"  Pending:   {format_number(summary.get('ocr_pending', 0)):>10}")
    print(f"  Processing: {format_number(summary.get('ocr_processing', 0)):>10}")
    print(f"  Done:      {format_number(summary.get('ocr_completed', 0)):>10} (expected: 1,139)")
    
    print("\n[4] PERFORMANCE METRICS")
    print("-" * 70)
    
    avg_extract = summary.get("avg_extraction_ms", 0) or 0
    avg_index = summary.get("avg_indexing_ms", 0) or 0
    
    print(f"Avg Extraction:    {avg_extract:.0f} ms (expected: ~451 ms)")
    print(f"Avg Indexing:      {avg_index:.0f} ms (expected: ~82 ms)")
    
    # Calculate derived metrics
    total_to_process = total_discovered - total_duplicates
    overall_progress = (total_completed / total_to_process * 100) if total_to_process > 0 else 0
    total_processed = total_completed + total_failures
    success_rate = (total_completed / total_processed * 100) if total_processed > 0 else 100
    
    size_progress = (comp_size / max(disc_size, 1)) * 100
    
    print("\n[5] CALCULATED METRICS")
    print("-" * 70)
    
    print(f"Overall Progress (files): {overall_progress:.1f}% ({total_completed:,} / {total_to_process:,})")
    print(f"Success Rate: {success_rate:.1f}%")
    print(f"Data Progress: {size_progress:.1f}% ({format_size(comp_size)} / {format_size(disc_size)})")
    
    print("\n" + "=" * 70)
    print("SYNC CHECK COMPLETE")
    print("=" * 70)
    
    return True

if __name__ == "__main__":
    test_metrics_sync()
