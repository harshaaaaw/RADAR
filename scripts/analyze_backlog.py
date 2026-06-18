#!/usr/bin/env python3
"""Analyze backlog and estimate ETAs per pipeline stage.
Reads DB at D:/DocumentSearch/queue/queues.db and config/config.yaml.
"""
import sqlite3
from pathlib import Path
import yaml

DB_PATH = Path('D:/DocumentSearch/queue/queues.db')
CONFIG_PATH = Path('config/config.yaml')

# Conservative defaults (seconds)
DEFAULT_EXTRACTION_SEC = 10
DEFAULT_INDEXING_SEC = 1
DEFAULT_OCR_SEC = 5

def read_config():
    cfg = yaml.safe_load(CONFIG_PATH.read_text())
    # extraction workers
    extraction_workers = cfg.get('extraction', {}).get('total_workers', 8)
    indexing_workers = cfg.get('indexing', {}).get('num_workers', 4) if cfg.get('indexing') else cfg.get('indexing', {}).get('num_workers', 4)
    ocr_workers = cfg.get('ocr', {}).get('initial_workers', 4) if cfg.get('ocr') else cfg.get('ocr', {}).get('initial_workers', 4)
    # fallback to multiple possible keys
    if isinstance(indexing_workers, dict):
        indexing_workers = cfg.get('indexing', {}).get('num_workers', 4)
    return int(extraction_workers), int(indexing_workers), int(ocr_workers)


def seconds_to_human(s: float) -> str:
    if s <= 0:
        return "0s"
    m, sec = divmod(int(s), 60)
    h, m = divmod(m, 60)
    parts = []
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    parts.append(f"{sec}s")
    return ' '.join(parts)


def analyze():
    if not DB_PATH.exists():
        print('DB not found:', DB_PATH)
        return

    extraction_workers, indexing_workers, ocr_workers = read_config()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Counts
    discovered_total = c.execute('SELECT COUNT(*) as cnt FROM discovered_files').fetchone()['cnt']
    completed_total = c.execute('SELECT COUNT(*) as cnt FROM completed_files WHERE is_duplicate = 0').fetchone()['cnt']

    extraction_pending = c.execute("SELECT COUNT(*) as cnt FROM extraction_queue WHERE status IN ('pending','processing')").fetchone()['cnt']
    indexing_pending = c.execute("SELECT COUNT(*) as cnt FROM indexing_queue WHERE status IN ('pending','processing')").fetchone()['cnt']
    ocr_pending = c.execute("SELECT COUNT(*) as cnt FROM ocr_queue WHERE status IN ('pending','processing')").fetchone()['cnt']

    # Average times in ms from completed_files (fallback to defaults)
    avg_extract_ms = c.execute('SELECT AVG(extraction_time_ms) as avg_ms FROM completed_files WHERE extraction_time_ms > 0').fetchone()['avg_ms']
    avg_index_ms = c.execute('SELECT AVG(indexing_time_ms) as avg_ms FROM completed_files WHERE indexing_time_ms > 0').fetchone()['avg_ms']

    avg_extract = (avg_extract_ms / 1000.0) if avg_extract_ms and avg_extract_ms > 0 else DEFAULT_EXTRACTION_SEC
    avg_index = (avg_index_ms / 1000.0) if avg_index_ms and avg_index_ms > 0 else DEFAULT_INDEXING_SEC
    avg_ocr = DEFAULT_OCR_SEC

    # ETA calculations (simple, per-stage remaining / workers * avg_time)
    eta_extract = (extraction_pending * avg_extract) / max(extraction_workers, 1)
    eta_index = (indexing_pending * avg_index) / max(indexing_workers, 1)
    eta_ocr = (ocr_pending * avg_ocr) / max(ocr_workers, 1)

    total_remaining_files = extraction_pending + indexing_pending + ocr_pending

    print('=== Backlog Summary ===')
    print(f'Discovered total: {discovered_total:,}')
    print(f'Completed (searchable): {completed_total:,}')
    print(f'Total remaining in pipeline: {total_remaining_files:,}\n')

    print('Stage breakdown:')
    print(f'  Extraction pending/processing: {extraction_pending:,} (workers: {extraction_workers})')
    print(f'  Indexing pending/processing:   {indexing_pending:,} (workers: {indexing_workers})')
    print(f'  OCR pending/processing:        {ocr_pending:,} (workers: {ocr_workers})\n')

    print('Average processing times used (sec):')
    print(f'  Extraction avg: {avg_extract:.2f}s')
    print(f'  Indexing avg:   {avg_index:.2f}s')
    print(f'  OCR avg (est):  {avg_ocr:.2f}s\n')

    print('Estimated time to clear backlog per stage:')
    print(f'  Extraction ETA: {seconds_to_human(eta_extract)}')
    print(f'  Indexing ETA:   {seconds_to_human(eta_index)}')
    print(f'  OCR ETA:        {seconds_to_human(eta_ocr)}')

    # Conservative total wall-clock ETA: assume stages can run in parallel, take max
    wall_clock_eta = max(eta_extract, eta_index, eta_ocr)
    print(f'\nEstimated wall-clock time to clear all current pipeline work (parallel): {seconds_to_human(wall_clock_eta)}')

    # Also compute serial ETA if everything had to be processed through remaining stages sequentially
    serial_eta = eta_extract + eta_index + eta_ocr
    print(f'Serial ETA (sum of stages): {seconds_to_human(serial_eta)}')

    # Show top blockers: largest files still pending extraction or indexing
    print('\nTop 10 largest files pending extraction:')
    for r in c.execute("SELECT d.file_path as file_path, d.file_size as file_size FROM extraction_queue e JOIN discovered_files d ON e.file_id=d.id WHERE e.status IN ('pending','processing') ORDER BY d.file_size DESC LIMIT 10"):
        print(f"  {r['file_size']:,} bytes - {r['file_path']}")

    print('\nTop 10 largest files pending indexing:')
    for r in c.execute("SELECT d.file_path as file_path, d.file_size as file_size FROM indexing_queue i JOIN discovered_files d ON i.file_id=d.id WHERE i.status IN ('pending','processing') ORDER BY d.file_size DESC LIMIT 10"):
        print(f"  {r['file_size']:,} bytes - {r['file_path']}")

    conn.close()

if __name__ == '__main__':
    analyze()
