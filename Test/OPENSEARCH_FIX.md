# OpenSearch Configuration Fix

## Issue Resolved

**Problem:** OpenSearch failed to start with error:
```
java.lang.IllegalArgumentException: node settings must not contain any index level settings
```

**Root Cause:** The opensearch.yml configuration file contained index-level settings that should only be applied per-index, not at the node level.

## Invalid Settings (Removed)

These settings were causing the startup failure:

```yaml
# ❌ WRONG - These are index-level settings, not node-level
index.translog.durability: async
index.translog.sync_interval: 5s
index.translog.flush_threshold_size: 1gb
index.merge.scheduler.max_thread_count: 8
```

## How to Apply Index-Level Settings

Index-level settings should be applied when creating the index via the OpenSearch client in Python:

```python
# In opensearch_client.py or during index creation
index_settings = {
    "settings": {
        "index": {
            "refresh_interval": "30s",  # During bulk indexing
            "translog": {
                "durability": "async",
                "sync_interval": "5s",
                "flush_threshold_size": "1gb"
            },
            "merge": {
                "scheduler": {
                    "max_thread_count": 8
                }
            }
        },
        "number_of_shards": 5,
        "number_of_replicas": 1
    },
    "mappings": { ... }
}

client.indices.create(index="enterprise_documents", body=index_settings)
```

## Corrected opensearch.yml

The fixed configuration only contains node-level settings:

```yaml
# ✅ Node-level settings only
cluster.name: enterprise-document-search
node.name: node-1
network.host: localhost
http.port: 9200
discovery.type: single-node
bootstrap.memory_lock: false

# Thread pools, circuit breakers, etc.
thread_pool:
  write:
    size: 32
    queue_size: 2000

indices.breaker.total.limit: 85%
indices.memory.index_buffer_size: 20%
```

## Verification

After fixing the configuration:

1. **Restart OpenSearch:**
   ```powershell
   nssm restart OpenSearch2
   ```

2. **Wait 30-60 seconds**, then test:
   ```powershell
   curl http://localhost:9200
   ```

3. **Run system check:**
   ```powershell
   python src/main.py check
   ```

You should see:
```
✓ OpenSearch 2.12.0: OK
✓ All services are running!
```

## Updated Files

- ✅ `C:\opensearch-2.12.0\config\opensearch.yml` - Fixed with node-level settings only
- ✅ `config/opensearch.yml` (project template) - Updated to remove invalid settings

## Next Steps

The application will apply index-level settings programmatically when creating the `enterprise_documents` index during initialization.

---

**Status:** ✅ RESOLVED - OpenSearch is now running successfully!
