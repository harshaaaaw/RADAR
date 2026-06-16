"""
Re-tag documents that have garbage in key_names / location_mentioned / amount_found.
Runs against the LIVE OpenSearch index directly, finds corrupted tagged docs,
and re-queues them for fresh tagging using the fixed TaggingEngine.

Usage:
    python retag_dirty_docs.py [--dry-run] [--limit 1000] [--batch 50]
"""
import sys, os, argparse, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

import re
from opensearchpy import OpenSearch
import redis

# ─── Garbage detection patterns (mirrors TaggingEngine._is_garbage_entity) ──
_SHORT_UPPER = re.compile(r'^[A-Z]{1,4}$')
_FIN_CODE = re.compile(r'^[A-Z0-9]{6,}$')
_NUMBER = re.compile(r'^-?\d[\d.,\-]*$')
_SCI_NUM = re.compile(r'^-?\d+\.?\d*[Ee][+\-]?\d+$')
_CELL_REF = re.compile(r'\$[A-Z]+\$?\d+|^[A-Z]+\d+:[A-Z]+\d+$|^col_')
_GARBAGE_WORDS = {
    'colomn', 'column', 'debit', 'credit', 'balance', 'total', 'amount', 
    'date', 'type', 'rate', 'line', 'description', 'text', 'list',
    'ledger', 'journal', 'account', 'transaction', 'source', 'pages',
    'document', 'entry', 'posting', 'period', 'fiscal', 'budget',
    'actual', 'variance', 'currency', 'accrual', 'invoice', 'receipt',
}

def is_garbage(val):
    if not val or len(val) < 2: return True
    if len(val) > 80: return True
    alpha = sum(1 for c in val if c.isalpha())
    if alpha < 2: return True
    stripped = val.strip()
    if _SHORT_UPPER.match(stripped) and len(stripped) <= 4: return True
    if _FIN_CODE.match(stripped): return True
    if _NUMBER.match(stripped): return True
    if _SCI_NUM.match(stripped): return True
    if _CELL_REF.search(stripped): return True
    if stripped.lower().split()[0] in _GARBAGE_WORDS: return True
    if re.search(r'Web\s*Page|www\.|\.com\b', stripped, re.IGNORECASE): return True
    return False

def doc_has_garbage(source):
    """Return True if any entity field contains garbage values."""
    for field in ('key_names', 'location_mentioned', 'important_dates'):
        values = source.get(field) or []
        if isinstance(values, str):
            values = [values]
        for v in values:
            if is_garbage(str(v)):
                return True
    return False

def main():
    parser = argparse.ArgumentParser(description='Re-tag docs with garbage entities')
    parser.add_argument('--dry-run', action='store_true', help='Count only, no changes')
    parser.add_argument('--limit', type=int, default=50000, help='Max docs to process')
    parser.add_argument('--batch', type=int, default=100, help='Scroll batch size')
    parser.add_argument('--requeue', action='store_true', help='Push to tagging queue (default: fix in place)')
    args = parser.parse_args()

    print(f"Re-tagging dirty docs (dry_run={args.dry_run}, limit={args.limit})")

    os_client = OpenSearch(hosts=[{'host': 'localhost', 'port': 9200}], use_ssl=False, timeout=30)
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

    # Scroll through tagged docs (those with category field set)
    query = {
        'query': {'exists': {'field': 'category'}},
        '_source': ['key_names', 'location_mentioned', 'amount_found', 'important_dates',
                    'file_name', 'file_hash', 'file_id', 'file_path', 'main_content',
                    'ocr_content', 'embedded_content', 'file_type', 'mime_type'],
        'size': args.batch,
    }

    dirty_count = 0
    clean_count = 0
    fixed_count = 0
    scroll_id = None

    try:
        resp = os_client.search(index='enterprise_documents', body=query, scroll='5m')
        scroll_id = resp['_scroll_id']
        hits = resp['hits']['hits']
        total = resp['hits']['total']['value']
        print(f"Total tagged docs: {total}")

        processed = 0
        while hits and processed < args.limit:
            for hit in hits:
                if processed >= args.limit:
                    break
                processed += 1
                src = hit['_source']
                doc_id = hit['_id']

                if doc_has_garbage(src):
                    dirty_count += 1
                    fname = src.get('file_name', doc_id)[:60]

                    if args.dry_run:
                        # Show a sample of garbage
                        garbages = []
                        for field in ('key_names', 'location_mentioned'):
                            vals = src.get(field) or []
                            for v in vals:
                                if is_garbage(str(v)):
                                    garbages.append(f"{field}={v!r}")
                        if dirty_count <= 5:
                            print(f"  DIRTY: {fname}")
                            for g in garbages[:3]:
                                print(f"    garbage: {g}")
                    elif args.requeue:
                        # Push back to tagging queue for reprocessing
                        file_hash = src.get('file_hash', '')
                        file_id_raw = src.get('file_id', 0)
                        try:
                            file_id = int(file_id_raw or 0)
                        except (ValueError, TypeError):
                            file_id = 0
                        file_path = src.get('file_path', '')
                        import json
                        item = json.dumps({
                            'id': file_id,
                            'file_id': file_id,
                            'file_path': file_path,
                            'file_hash': file_hash,
                            'doc_id': doc_id,
                            'priority': 8,  # high priority re-tag
                            'retry_count': 0,
                            'status': 'pending',
                            'added_at': time.time(),
                        })
                        r.lpush('docsearch:queue:tagging', item)
                        fixed_count += 1
                    else:
                        # Direct fix: re-run entity extraction inline
                        try:
                            from tagging.tagging_engine import TaggingEngine
                            from tagging.tagging_models import TaggingRequest
                            from pathlib import Path
                            engine = TaggingEngine()
                            req = TaggingRequest(
                                file_id=int(src.get('file_id', 0) or 0),
                                file_path=str(src.get('file_path', '') or ''),
                                file_name=str(src.get('file_name', '') or ''),
                                file_hash=str(src.get('file_hash', '') or ''),
                                doc_id=doc_id,
                                file_type=str(src.get('file_type', '') or ''),
                                mime_type=str(src.get('mime_type', '') or ''),
                                main_content=str(src.get('main_content', '') or ''),
                                ocr_content=str(src.get('ocr_content', '') or ''),
                                embedded_content=str(src.get('embedded_content', '') or ''),
                                metadata={},
                            )
                            result = engine.tag(req)
                            update = result.to_document_update()
                            os_client.update(
                                index='enterprise_documents',
                                id=doc_id,
                                body={'doc': update}
                            )
                            fixed_count += 1
                            if fixed_count % 100 == 0:
                                print(f"  Fixed {fixed_count} docs so far... (dirty={dirty_count}, processed={processed})")
                        except Exception as e:
                            print(f"  ERROR fixing {doc_id}: {e}")
                else:
                    clean_count += 1

            if processed >= args.limit:
                break
            resp = os_client.scroll(scroll_id=scroll_id, scroll='5m')
            scroll_id = resp['_scroll_id']
            hits = resp['hits']['hits']

    finally:
        if scroll_id:
            try:
                os_client.clear_scroll(scroll_id=scroll_id)
            except Exception:
                pass

    print(f"\n{'='*50}")
    print(f"Processed: {processed} docs")
    print(f"Dirty (garbage entities): {dirty_count} ({100*dirty_count/max(processed,1):.1f}%)")
    print(f"Clean: {clean_count}")
    if not args.dry_run:
        print(f"Fixed/Requeued: {fixed_count}")
    print(f"{'='*50}")

if __name__ == '__main__':
    main()
