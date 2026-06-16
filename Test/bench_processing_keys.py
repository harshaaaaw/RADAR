"""Quick benchmark for the optimized processing key lookup."""
import redis
import time
r = redis.Redis(decode_responses=True)

# Keys we need
PREFIXES = [
    'docsearch:processing:indexing',
    'docsearch:processing:ocr', 
    'docsearch:processing:extraction',
]

_cache = {}
_cache_ts = {}
TTL = 30.0

def get_worker_keys_cached(prefix):
    now = time.time()
    if now - _cache_ts.get(prefix, 0) < TTL and prefix in _cache:
        return _cache[prefix]
    keys = list(r.scan_iter(match=f'{prefix}:*', count=1000))
    _cache[prefix] = keys
    _cache_ts[prefix] = now
    return keys

print("=== COLD CACHE (first SCAN) ===")
t0 = time.time()
for pfx in PREFIXES:
    t1 = time.time()
    keys = get_worker_keys_cached(pfx)
    t2 = time.time()
    # Pipeline HLEN
    if keys:
        pipe = r.pipeline(transaction=False)
        for k in keys:
            pipe.hlen(k)
        counts = pipe.execute()
        total = sum(c for c in counts if isinstance(c, int))
    else:
        total = 0
    t3 = time.time()
    print(f"  {pfx}: scan={t2-t1:.3f}s, hlen_pipe={t3-t2:.3f}s, "
          f"keys={len(keys)}, items={total}")
cold_total = time.time() - t0
print(f"  COLD TOTAL: {cold_total:.3f}s\n")

print("=== WARM CACHE (cached keys) ===")
t0 = time.time()
for pfx in PREFIXES:
    t1 = time.time()
    keys = get_worker_keys_cached(pfx)
    t2 = time.time()
    if keys:
        pipe = r.pipeline(transaction=False)
        for k in keys:
            pipe.hlen(k)
        counts = pipe.execute()
        total = sum(c for c in counts if isinstance(c, int))
    else:
        total = 0
    t3 = time.time()
    print(f"  {pfx}: cache_hit={t2-t1:.6f}s, hlen_pipe={t3-t2:.3f}s, "
          f"keys={len(keys)}, items={total}")
warm_total = time.time() - t0
print(f"  WARM TOTAL: {warm_total:.3f}s")
print(f"\n  Speedup: {cold_total/max(warm_total,0.001):.1f}x (cold->warm)")
