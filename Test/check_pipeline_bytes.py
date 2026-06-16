import redis
r = redis.Redis(decode_responses=True)

d = int(r.get('docsearch:counter:discovered_bytes') or 0)
c = int(r.get('docsearch:counter:completed_bytes') or 0)
print(f'discovered_bytes: {d}')
print(f'completed_bytes: {c}')
print(f'delta: {d - c} bytes ({(d-c)/1024:.2f} KB)')

# File 1 is the zombie - its bytes were counted in discovered but never in completed
f1_size = r.hget('docsearch:files:1', 'file_size')
print(f'file_id 1 size: {f1_size}')
print(f'file_id 1 in completed_file_ids: {r.sismember("docsearch:completed_file_ids", "1")}')

# The fix: discovered_bytes was incremented for the duplicate but completed_bytes wasn't
# We need to either:
#   a) Decrement discovered_bytes by the duplicate's size
#   b) Or add the file to completed (since it IS in OpenSearch)
# Option (b) is more correct since the file IS indexed

# Check how many files in completed vs discovered
disc = int(r.get('docsearch:counter:discovered') or 0)
comp = int(r.get('docsearch:counter:root_completed') or 0)
print(f'\ndiscovered: {disc}, completed: {comp}, difference: {disc - comp}')

# Also check counter:extraction_completed vs root_completed
ext = int(r.get('docsearch:counter:extraction_completed') or 0)
print(f'extraction_completed: {ext}')

# The race-condition duplicate incremented discovered/discovered_bytes/extraction_completed
# but was never routed through completion
