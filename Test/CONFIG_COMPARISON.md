# ⚡ **QUICK REFERENCE: MINIMAL vs AWS CONFIG**

---

## 📊 **AT A GLANCE**

### **Current System (Minimal - 16GB)**
```yaml
✅ CORRECT for your local testing machine
- 8 cores / 16GB RAM
- 2 Tika servers × 1GB
- 4 extraction workers
- 2 indexing workers
- 2 OCR workers
- ~10 files/sec throughput
```

### **Future System (AWS - 256GB)**
```yaml
✅ USE config_aws.yaml
- 64 vCPUs / 256GB RAM
- 12 Tika servers × 6-12GB
- 40 extraction workers
- 10 indexing workers
- 4-20 OCR workers
- ~500-1000 files/sec throughput
```

---

## 🎯 **WORKER ALLOCATION**

| Component | Minimal (16GB) | AWS (256GB) | Why? |
|-----------|---------------|-------------|------|
| **Discovery** | 1 worker | 8 workers | I/O bound, scales linearly |
| **Extraction** | 4 workers | 40 workers | **BOTTLENECK** - needs most CPUs |
| **Indexing** | 2 workers | 10 workers | Fast, doesn't need many |
| **OCR** | 2 workers | 4→20 workers | Slow, scales after extraction |
| **Tika Servers** | 2 × 1GB | 12 × 6-12GB | **CRITICAL** - needs RAM |

---

## 💾 **MEMORY ALLOCATION**

### **Minimal (16GB Total)**
```
Tika:     2GB   (12%)
Python:   4GB   (25%)
OS:       4GB   (25%)
Free:     6GB   (38%)
```

### **AWS (256GB Total)**
```
Tika:     104GB (40%)  ← 12 servers
Python:   40GB  (16%)  ← 60 workers
OpenSearch: 60GB (23%)  ← If local
OS:       40GB  (16%)
NLP:      16GB  (6%)
```

---

## 🚀 **DEPLOYMENT COMMANDS**

### **Minimal System (Current)**
```bash
# Already running correctly
python src/main.py start --config config/config_minimal.yaml
```

### **AWS System (Future)**
```bash
# 1. Start Tika servers (12 instances)
./bin/start-tika-aws.sh

# 2. Start system with AWS config
python src/main.py start --config config/config_aws.yaml

# 3. Monitor
python src/main.py status
```

---

## 📈 **EXPECTED PERFORMANCE**

| Metric | Minimal | AWS | Improvement |
|--------|---------|-----|-------------|
| **Files/sec** | 10 | 500-1000 | **50-100x** |
| **CPU Usage** | 50% | 75-85% | Better utilization |
| **RAM Usage** | 60% | 80% | Better utilization |
| **Tika Crashes** | Possible | None | Stable |
| **1M files** | ~27 hours | ~0.5-1 hour | **27-54x faster** |

---

## ⚙️ **KEY CONFIGURATION DIFFERENCES**

### **1. Tika Servers**

**Minimal:**
```yaml
tika:
  instances:
    - {port: 9998, memory_mb: 1024}  # 1GB
    - {port: 9999, memory_mb: 1024}  # 1GB
```

**AWS:**
```yaml
tika:
  instances:
    # 12 servers with 6-12GB each
    - {port: 9998, memory_mb: 6144}   # 6GB
    - {port: 9999, memory_mb: 6144}   # 6GB
    - {port: 10000, memory_mb: 6144}  # 6GB
    - {port: 10001, memory_mb: 8192}  # 8GB
    - {port: 10002, memory_mb: 8192}  # 8GB
    - {port: 10003, memory_mb: 8192}  # 8GB
    - {port: 10004, memory_mb: 8192}  # 8GB
    - {port: 10005, memory_mb: 10240} # 10GB
    - {port: 10006, memory_mb: 10240} # 10GB
    - {port: 10007, memory_mb: 10240} # 10GB
    - {port: 10008, memory_mb: 12288} # 12GB
    - {port: 10009, memory_mb: 12288} # 12GB
```

---

### **2. Worker Counts**

**Minimal:**
```yaml
discovery.num_workers: 1
extraction.total_workers: 4
  fast_track: 2
  standard_track: 2
  heavy_track: 0      # Disabled
  extreme_track: 0    # Disabled
indexing.num_workers: 2
ocr.initial_workers: 2
```

**AWS:**
```yaml
discovery.num_workers: 8
extraction.total_workers: 40
  fast_track: 12
  standard_track: 16
  heavy_track: 8      # Enabled
  extreme_track: 4    # Enabled
indexing.num_workers: 10
ocr.initial_workers: 4
ocr.post_indexing_workers: 20
```

---

### **3. Batch Sizes**

**Minimal:**
```yaml
indexing.opensearch.initial_batch_size: 100
indexing.opensearch.max_batch_size: 500
```

**AWS:**
```yaml
indexing.opensearch.initial_batch_size: 2000
indexing.opensearch.max_batch_size: 10000
```

---

### **4. Memory Thresholds**

**Minimal:**
```yaml
orchestrator.memory:
  warning_threshold_gb: 12   # For 16GB system
  critical_threshold_gb: 14
  emergency_threshold_gb: 15
```

**AWS:**
```yaml
orchestrator.memory:
  warning_threshold_gb: 200  # For 256GB system
  critical_threshold_gb: 230
  emergency_threshold_gb: 245
```

---

### **5. NLP**

**Minimal:**
```yaml
nlp:
  enabled: false  # Disabled to save RAM
```

**AWS:**
```yaml
nlp:
  enabled: true   # Enabled for better accuracy
  model_path: "en_core_web_lg"  # Large model
```

---

## 🎯 **WHEN TO USE WHICH CONFIG**

### **Use `config_minimal.yaml` when:**
- ✅ Testing locally on 16GB machine
- ✅ Development and debugging
- ✅ Small datasets (<10K files)
- ✅ Limited resources

### **Use `config_aws.yaml` when:**
- ✅ Production deployment on AWS
- ✅ 64 vCPUs / 256GB RAM available
- ✅ Large datasets (>100K files)
- ✅ Need high throughput

---

## 📝 **CONFIGURATION FILES**

| File | Purpose | System |
|------|---------|--------|
| `config/config_minimal.yaml` | Current config | 16GB local |
| `config/config.yaml` | Same as minimal | 16GB local |
| `config/config_aws.yaml` | AWS production | 256GB AWS |

---

## ⚠️ **COMMON MISTAKES**

### **❌ DON'T:**
- Use AWS config on 16GB machine (will crash)
- Use minimal config on 256GB AWS (waste of resources)
- Allocate 100% of CPUs to workers (leave 2-4 for OS)
- Give Tika servers <4GB on AWS (will crash)

### **✅ DO:**
- Match config to your hardware
- Leave headroom for OS and buffers
- Monitor memory usage
- Scale OCR workers after extraction

---

## 🚀 **QUICK START**

### **Current System (Minimal)**
```bash
# You're already using this correctly!
python src/main.py start
```

### **Future AWS System**
```bash
# When you deploy to AWS:
python src/main.py start --config config/config_aws.yaml
```

---

## 📊 **RESOURCE CALCULATOR**

**Formula for any system:**

```python
# CPUs
discovery_workers = max(1, cpus * 0.125)      # 12.5%
extraction_workers = max(4, cpus * 0.625)     # 62.5%
indexing_workers = max(2, cpus * 0.156)       # 15.6%
ocr_workers = max(2, cpus * 0.062)            # 6.2%

# RAM
tika_ram_gb = ram_gb * 0.40                   # 40%
python_ram_gb = ram_gb * 0.16                 # 16%
opensearch_ram_gb = ram_gb * 0.23             # 23% (if local)
os_ram_gb = ram_gb * 0.16                     # 16%

# Tika servers
num_tika_servers = max(2, extraction_workers / 3.5)
ram_per_tika = tika_ram_gb / num_tika_servers
```

**Examples:**

| System | Discovery | Extraction | Indexing | OCR | Tika Servers |
|--------|-----------|------------|----------|-----|--------------|
| **16GB / 8 CPU** | 1 | 4 | 2 | 2 | 2 × 1GB |
| **64GB / 16 CPU** | 2 | 10 | 2 | 2 | 3 × 8GB |
| **128GB / 32 CPU** | 4 | 20 | 5 | 4 | 6 × 8GB |
| **256GB / 64 CPU** | 8 | 40 | 10 | 8 | 12 × 8GB |
| **512GB / 128 CPU** | 16 | 80 | 20 | 16 | 24 × 8GB |

---

## ✅ **SUMMARY**

**Your current minimal config is CORRECT for 16GB!**

**When you move to AWS 64 vCPU / 256GB:**
1. Use `config/config_aws.yaml`
2. Start 12 Tika servers
3. Expect 50-100x better performance
4. Monitor for stability

**The config is already created and ready to use!** 🚀

---

**Files Created:**
- ✅ `config/config_aws.yaml` - AWS configuration
- ✅ `AWS_OPTIMAL_CONFIG.md` - Detailed explanation
- ✅ `AWS_DEPLOYMENT_GUIDE.md` - Deployment steps
- ✅ `ROOT_CAUSE_ANALYSIS_AWS.md` - Analysis (for reference)

**Status:** ✅ **READY FOR FUTURE AWS DEPLOYMENT**
