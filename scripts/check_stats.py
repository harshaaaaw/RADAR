import os
import sys
import json

# Ensure src is importable
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

from core.queue_manager import get_queue_manager

qm = get_queue_manager()
qs = qm.get_queue_statistics()
ss = qm.get_size_statistics()

print('QUEUE_STATS:')
print(json.dumps(qs, indent=2))
print('\nSIZE_STATS:')
print(json.dumps(ss, indent=2))

# Checks
discovery_total = qs.get('discovery', {}).get('total')
discovered_files = ss.get('discovered', {}).get('files')
completed_total = qs.get('completed', {}).get('total_completed')
searchable_files = ss.get('searchable', {}).get('files')

print('\nChecks:')
print('discovery_total == discovered_files ->', discovery_total, discovered_files, discovery_total == discovered_files)
print('completed_total == searchable_files ->', completed_total, searchable_files, completed_total == searchable_files)

# In-pipeline components
extraction = qs.get('extraction', {})
if isinstance(extraction, dict) and any(isinstance(v, dict) for v in extraction.values()):
    ext_pending = sum(((v.get('pending') or 0) + (v.get('processing') or 0)) for v in extraction.values())
else:
    ext_pending = (extraction.get('pending') or 0) + (extraction.get('processing') or 0) if extraction else 0

indexing_pending = (qs.get('indexing', {}) .get('pending') or 0) + (qs.get('indexing', {}).get('processing') or 0)
ocr_pending = (qs.get('ocr', {}).get('pending') or 0) + (qs.get('ocr', {}).get('processing') or 0)

print('in_pipeline component sum (files):', ext_pending + indexing_pending + ocr_pending)
print('size_stats in_pipeline files:', ss.get('in_pipeline', {}).get('files'))

print('\nDone')
