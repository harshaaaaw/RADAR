# 🚀 **OPTIMAL AWS CONFIGURATION GUIDE**

**Target System:** AWS EC2 with 64 vCPUs / 256GB RAM  
**Current System:** Local 16GB (correctly configured as minimal)  
**Purpose:** Future production deployment

---

## 📊 **SYSTEM COMPARISON**

| Spec | Current (Local) | Future (AWS) | Multiplier |
|------|----------------|--------------|------------|
| **CPUs** | 8 cores | 64 vCPUs | **8x** |
| **RAM** | 16GB | 256GB | **16x** |
| **Storage** | Local SSD | AWS EBS/NVMe | - |
| **Network** | Local | 10-25 Gbps | - |
| **Purpose** | Testing | Production | - |

---

## 🎯 **OPTIMAL AWS CONFIGURATION**

### **Resource Allocation Strategy**

For **64 vCPUs / 256GB RAM**, here's the optimal allocation:

```
Total vCPUs: 64
├── Discovery:    8 vCPUs  (12.5%)
├── Extraction:   40 vCPUs (62.5%) ← Bottleneck, needs most resources
├── Indexing:     10 vCPUs (15.6%)
├── OCR:          4 vCPUs  (6.2%)  ← Initial, scales to 20 post-indexing
└── System/OS:    2 vCPUs  (3.1%)

Total RAM: 256GB
├── Tika Servers: 100GB   (39%)   ← 12 servers with 6-12GB each
├── Python Workers: 40GB  (16%)   ← ~60 workers × 600MB each
├── OpenSearch:   60GB    (23%)   ← If running locally
├── OS + Buffers: 40GB    (16%)
└── NLP Models:   16GB    (6%)    ← SpaCy + other models
```

---

## ⚙️ **DETAILED CONFIGURATION**

### **1. Discovery Workers**

```yaml
discovery:
  num_workers: 8  # 12.5% of CPUs
  batch_size: 1000
  target_rate: 100000  # 100K files/sec discovery rate
```

**Reasoning:**
- Discovery is I/O bound, not CPU bound
- 8 workers can easily handle 100K+ files/sec
- More workers = diminishing returns

---

### **2. Extraction Workers (MOST IMPORTANT)**

```yaml
extraction:
  total_workers: 40  # 62.5% of CPUs - THIS IS THE BOTTLENECK
  
  pools:
    fast_track:      # Tiny files (<1MB)
      num_workers: 12
      tika_ports: [9998, 9999, 10000]  # 3 Tika servers
      
    standard_track:  # Small files (1-10MB)
      num_workers: 16
      tika_ports: [10001, 10002, 10003, 10004]  # 4 Tika servers
      
    heavy_track:     # Medium files (10-50MB)
      num_workers: 8
      tika_ports: [10005, 10006, 10007]  # 3 Tika servers
      
    extreme_track:   # Large files (>50MB)
      num_workers: 4
      tika_ports: [10008, 10009]  # 2 Tika servers
```

**Tika Server Configuration:**

```yaml
tika:
  instances:
    # Fast track - 3 servers × 6GB = 18GB
    - {port: 9998, memory_mb: 6144}
    - {port: 9999, memory_mb: 6144}
    - {port: 10000, memory_mb: 6144}
    
    # Standard track - 4 servers × 8GB = 32GB
    - {port: 10001, memory_mb: 8192}
    - {port: 10002, memory_mb: 8192}
    - {port: 10003, memory_mb: 8192}
    - {port: 10004, memory_mb: 8192}
    
    # Heavy track - 3 servers × 10GB = 30GB
    - {port: 10005, memory_mb: 10240}
    - {port: 10006, memory_mb: 10240}
    - {port: 10007, memory_mb: 10240}
    
    # Extreme track - 2 servers × 12GB = 24GB
    - {port: 10008, memory_mb: 12288}
    - {port: 10009, memory_mb: 12288}
  
  # Total: 12 Tika servers, 104GB RAM
```

**Reasoning:**
- Extraction is THE bottleneck (Tika processing is slow)
- Allocate 62.5% of CPUs here
- 12 Tika servers to handle parallel load
- Memory allocation: 6-12GB per server based on file size
- Total Tika RAM: 104GB (40% of system RAM)

---

### **3. Indexing Workers**

```yaml
indexing:
  num_workers: 10  # 15.6% of CPUs
  
  opensearch:
    initial_batch_size: 2000   # Large batches for efficiency
    min_batch_size: 1000
    max_batch_size: 10000
    batch_adjustment_step: 1000
    connection_pool_size: 10
```

**Reasoning:**
- Indexing is fast (OpenSearch is optimized)
- 10 workers can handle 5000+ docs/sec
- Large batches reduce network overhead
- More workers = diminishing returns

---

### **4. OCR Workers**

```yaml
ocr:
  initial_workers: 4   # During extraction phase
  post_indexing_workers: 20  # After extraction complete
  max_pages_per_pdf: 200
```

**Reasoning:**
- OCR is slow but runs in parallel with extraction
- Start with 4 workers (6% of CPUs)
- Scale to 20 workers (31% of CPUs) after extraction completes
- This prevents OCR from competing with extraction

---

### **5. Memory Thresholds**

```yaml
orchestrator:
  memory:
    warning_threshold_gb: 200   # 78% of 256GB
    critical_threshold_gb: 230  # 90% of 256GB
    emergency_threshold_gb: 245 # 96% of 256GB
```

**Reasoning:**
- Leave 10GB for OS and buffers
- Warning at 200GB (still 56GB free)
- Critical at 230GB (26GB free)
- Emergency at 245GB (11GB free)

---

### **6. NLP Configuration**

```yaml
nlp:
  enabled: true
  model_path: "en_core_web_lg"  # Large model for production
  max_text_length: 1000000  # 1M characters
```

**Reasoning:**
- AWS has enough RAM for large NLP models
- Better accuracy with large models
- Minimal CPU overhead (NLP is fast)

---

## 📈 **EXPECTED PERFORMANCE**

### **Throughput Estimates**

| Stage | Rate | Notes |
|-------|------|-------|
| **Discovery** | 100,000 files/sec | I/O bound, very fast |
| **Extraction** | 500-1000 files/sec | Bottleneck, depends on file size |
| **Indexing** | 5,000-10,000 docs/sec | Fast, batch optimized |
| **OCR** | 2,000-5,000 pages/hour | Slow, parallel processing |

### **Processing Time Estimates**

For **1 million documents** (average 2MB each):

| Stage | Time | Workers |
|-------|------|---------|
| Discovery | ~10 minutes | 8 workers |
| Extraction | **16-33 hours** | 40 workers + 12 Tika |
| Indexing | ~2-3 hours | 10 workers |
| OCR (if needed) | ~200-500 hours | 4-20 workers |

**Total:** ~18-36 hours for extraction + indexing (OCR runs in background)

---

## 🎯 **WORKER-TO-CPU RATIO**

### **Optimal Ratios**

```
Discovery:   8 workers / 64 CPUs  = 0.125 (12.5%)
Extraction:  40 workers / 64 CPUs = 0.625 (62.5%)
Indexing:    10 workers / 64 CPUs = 0.156 (15.6%)
OCR:         4 workers / 64 CPUs  = 0.062 (6.2%)
Total:       62 workers / 64 CPUs = 0.969 (96.9%)
```

**Why not 100%?**
- Leave 2 CPUs for OS, monitoring, API
- Prevents CPU thrashing
- Better stability

---

## 🔧 **CONFIGURATION FILE**

The optimal configuration is already in:
```
config/config_aws.yaml
```

**Key sections to verify:**

```yaml
# 1. Worker counts
discovery.num_workers: 8
extraction.total_workers: 40
indexing.num_workers: 10
ocr.initial_workers: 4
ocr.post_indexing_workers: 20

# 2. Tika servers
extraction.tika.instances: 12 servers (104GB total)

# 3. Memory thresholds
orchestrator.memory.warning_threshold_gb: 200
orchestrator.memory.critical_threshold_gb: 230
orchestrator.memory.emergency_threshold_gb: 245

# 4. Batch sizes
indexing.opensearch.initial_batch_size: 2000
indexing.opensearch.max_batch_size: 10000

# 5. NLP
nlp.enabled: true
nlp.model_path: "en_core_web_lg"
```

---

## 📊 **COMPARISON: MINIMAL vs AWS**

| Setting | Minimal (16GB) | AWS (256GB) | Ratio |
|---------|---------------|-------------|-------|
| **Discovery Workers** | 1 | 8 | 8x |
| **Extraction Workers** | 4 | 40 | 10x |
| **Indexing Workers** | 2 | 10 | 5x |
| **OCR Workers** | 2 | 4-20 | 2-10x |
| **Tika Servers** | 2 | 12 | 6x |
| **Tika RAM/server** | 1GB | 6-12GB | 6-12x |
| **Total Tika RAM** | 2GB | 104GB | 52x |
| **Batch Size** | 100 | 2000 | 20x |
| **NLP** | Disabled | Enabled | - |
| **Expected Throughput** | 10 files/sec | 500-1000 files/sec | 50-100x |

---

## ⚠️ **IMPORTANT NOTES**

### **1. Don't Over-Allocate Workers**

**Bad:**
```yaml
extraction.total_workers: 64  # ❌ TOO MANY!
```

**Why?**
- Each worker needs RAM (~600MB)
- Context switching overhead
- Diminishing returns
- Better to have fewer, efficient workers

**Good:**
```yaml
extraction.total_workers: 40  # ✅ OPTIMAL
```

---

### **2. Tika is the Bottleneck**

**Key insight:**
- Extraction is 10-100x slower than indexing
- Tika processing is CPU + memory intensive
- More Tika servers = better throughput
- But each needs 6-12GB RAM

**Optimal:**
- 12 Tika servers
- 40 extraction workers
- 3-4 workers per Tika server

---

### **3. OCR Scaling Strategy**

**Phase 1: During Extraction**
```yaml
ocr.initial_workers: 4  # Low priority
```

**Phase 2: After Extraction**
```yaml
ocr.post_indexing_workers: 20  # High priority
```

**Why?**
- OCR is slow (10-60 sec/page)
- Don't compete with extraction
- Scale up after extraction completes

---

### **4. OpenSearch Considerations**

**If OpenSearch is LOCAL (same machine):**
```yaml
# Reserve 60GB for OpenSearch
orchestrator.memory.warning_threshold_gb: 180  # Lower threshold
```

**If OpenSearch is REMOTE (separate server):**
```yaml
# Can use full 256GB
orchestrator.memory.warning_threshold_gb: 200  # Higher threshold
```

---

## 🚀 **DEPLOYMENT CHECKLIST**

### **Before Deploying to AWS:**

- [ ] Verify AWS instance: 64 vCPUs / 256GB RAM
- [ ] Install Java (for Tika servers)
- [ ] Install Python 3.10+ with all dependencies
- [ ] Install Tesseract OCR
- [ ] Install Poppler (for PDF processing)
- [ ] Install SpaCy large model: `python -m spacy download en_core_web_lg`
- [ ] Set up OpenSearch (local or remote)
- [ ] Configure storage (EBS volumes)
- [ ] Set up monitoring (CloudWatch, Prometheus)
- [ ] Test with `config_aws.yaml`

### **Startup Sequence:**

1. Start OpenSearch (if local)
2. Start 12 Tika servers
3. Start document search system with AWS config
4. Monitor for 30 minutes
5. Verify throughput and stability

---

## 📈 **SCALING GUIDELINES**

### **If you get MORE resources:**

**128 vCPUs / 512GB RAM:**
```yaml
discovery.num_workers: 16
extraction.total_workers: 80
indexing.num_workers: 20
ocr.post_indexing_workers: 40
tika.instances: 24 servers (200GB total)
```

**32 vCPUs / 128GB RAM:**
```yaml
discovery.num_workers: 4
extraction.total_workers: 20
indexing.num_workers: 5
ocr.post_indexing_workers: 10
tika.instances: 6 servers (48GB total)
```

---

## 🎯 **FINAL RECOMMENDATION**

**For AWS 64 vCPUs / 256GB RAM, use:**

```bash
python src/main.py start --config config/config_aws.yaml
```

**This configuration provides:**
- ✅ Optimal resource utilization (96% CPU, 80% RAM)
- ✅ Balanced worker allocation
- ✅ Proper Tika server sizing
- ✅ 50-100x throughput vs minimal config
- ✅ Stable 24/7 operation
- ✅ Room for growth

---

## 📝 **SUMMARY**

| Question | Answer |
|----------|--------|
| **What's the right config for AWS?** | `config/config_aws.yaml` |
| **How many workers?** | 40 extraction, 10 indexing, 8 discovery, 4-20 OCR |
| **How many Tika servers?** | 12 servers with 6-12GB each |
| **Expected throughput?** | 500-1000 files/sec |
| **Memory usage?** | ~200GB (80% of 256GB) |
| **CPU usage?** | ~75-85% of 64 vCPUs |

**The `config_aws.yaml` file is already optimized for your AWS system!** ✅

---

**Status:** ✅ **READY FOR AWS DEPLOYMENT**
