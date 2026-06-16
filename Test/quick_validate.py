"""Quick dashboard sync validation - Redis raw vs get_queue_statistics() output"""
import sys
import redis
sys.path.insert(0, 'src')

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

# Get raw Redis counts
pipe = r.pipeline(transaction=False)
for stage in ['extraction', 'indexing', 'ocr']:
    for cat in ['tiny', 'small', 'medium', 'large']:
        pipe.zcard(f'docsearch:queue:{stage}:{cat}')
for stage in ['extraction', 'indexing', 'ocr']:
    for cat in ['tiny', 'small', 'medium', 'large']:
        pipe.scard(f'docsearch:processing:{stage}:{cat}')
for c in ['discovered', 'discovery:completed', 'extraction:completed', 'indexing:completed', 'ocr:completed', 'completed']:
    pipe.get(f'docsearch:counter:{c}')
pipe.get('docsearch:counter:failures:ocr_error')
results = pipe.execute()

idx = 0
raw = {}
for stage in ['extraction', 'indexing', 'ocr']:
    total = 0
    for cat in ['tiny', 'small', 'medium', 'large']:
        total += results[idx] or 0
        idx += 1
    raw[f'{stage}_pending'] = total

for stage in ['extraction', 'indexing', 'ocr']:
    total = 0
    for cat in ['tiny', 'small', 'medium', 'large']:
        total += results[idx] or 0
        idx += 1
    raw[f'{stage}_processing'] = total

for c in ['discovered', 'discovery:completed', 'extraction:completed', 'indexing:completed', 'ocr:completed', 'completed']:
    val = results[idx]
    raw[c.replace(':', '_')] = int(val) if val else 0
    idx += 1

raw['total_failures'] = int(results[idx]) if results[idx] else 0

# Now get get_queue_statistics() output
from core.queue_manager import get_queue_manager
qm = get_queue_manager()
qs = qm.get_queue_statistics()

def si(v):
    try: return int(v) if v else 0
    except: return 0

# Build dashboard summary from qs
et = qs.get('extraction_total', {}) or {}
ix = qs.get('indexing', {}) or {}
oc = qs.get('ocr', {}) or {}
di = qs.get('discovery', {}) or {}
co = qs.get('completed', {}) or {}

dash = {
    'discovered': si(di.get('total')),
    'discovery_completed': si(di.get('completed')),
    'extraction_pending': si(et.get('pending')),
    'extraction_processing': si(et.get('processing')),
    'extraction_completed': si(et.get('completed')),
    'indexing_pending': si(ix.get('pending')),
    'indexing_processing': si(ix.get('processing')),
    'indexing_completed': si(ix.get('completed')),
    'ocr_pending': si(oc.get('pending')),
    'ocr_processing': si(oc.get('processing')),
    'ocr_completed': si(oc.get('completed')),
    'completed_total': si(co.get('total_completed') or co.get('total')),
    'total_failures': si(qs.get('total_failures')),
}

print("=" * 78)
print("DASHBOARD DATA SYNC VALIDATION")
print("=" * 78)
print(f"{'Metric':<35} {'Redis Raw':>14} {'Dashboard':>14} {'Match':>8}")
print("-" * 78)

comparisons = [
    ('discovered', raw['discovered'], dash['discovered']),
    ('discovery_completed', raw['discovery_completed'], dash['discovery_completed']),
    ('extraction_pending', raw['extraction_pending'], dash['extraction_pending']),
    ('extraction_processing', raw['extraction_processing'], dash['extraction_processing']),
    ('extraction_completed', raw['extraction_completed'], dash['extraction_completed']),
    ('indexing_pending', raw['indexing_pending'], dash['indexing_pending']),
    ('indexing_processing', raw['indexing_processing'], dash['indexing_processing']),
    ('indexing_completed', raw['indexing_completed'], dash['indexing_completed']),
    ('ocr_pending', raw['ocr_pending'], dash['ocr_pending']),
    ('ocr_processing', raw['ocr_processing'], dash['ocr_processing']),
    ('ocr_completed', raw['ocr_completed'], dash['ocr_completed']),
    ('completed_total', raw['completed'], dash['completed_total']),
    ('total_failures', raw['total_failures'], dash['total_failures']),
]

p, w, f = 0, 0, 0
for name, rv, dv in comparisons:
    if rv == dv:
        s = "PASS"; p += 1
    elif abs(rv - dv) <= max(10, rv * 0.03):
        s = "WARN"; w += 1
    else:
        s = "FAIL"; f += 1
    print(f"{name:<35} {rv:>14,} {dv:>14,} {s:>8}")

print("=" * 78)
print(f"RESULT: {p} PASS, {w} WARN, {f} FAIL")
if f == 0:
    print("ALL DASHBOARD METRICS SYNC WITH REDIS DATA")
print("=" * 78)
