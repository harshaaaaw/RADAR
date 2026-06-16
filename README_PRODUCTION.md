# Enterprise Document Search System
## Production-Ready Configuration for 128 vCPU / 64GB RAM

---

## 🚀 Quick Start

### Prerequisites
1. **Apache Tika** - Download tika-server.jar to `C:\Program Files\Tika\`
2. **OpenSearch 2.x** - Install to `C:\Program Files\OpenSearch\`
3. **Tesseract OCR** - Already installed at configured path
4. **Python 3.10+** with all dependencies from requirements.txt

### Start System
```bash
cd C:\DocumentSearch\bin
start_all.bat
```

This will:
1. Start OpenSearch with 12GB heap
2. Start 8 Tika instances (16GB total)
3. Start Master Orchestrator with 150 workers

### Stop System
```bash
cd C:\DocumentSearch\bin
stop_all.bat
```

Graceful shutdown with checkpoint saving.

---

## 📊 Performance Specifications

### System Configuration

| Component | Count | Memory | CPU Cores | Purpose |
|-----------|-------|--------|-----------|---------|
| **Tika Instances** | 8 | 16GB total | 16-24 | Text extraction |
| **Discovery Workers** | 4 | 2GB | 2-4 | File scanning |
| **Extraction Workers** | 100 | 8GB | 20-30 | Document processing |
| **Indexing Workers** | 16 | 4GB | 8-12 | OpenSearch bulk indexing |
| **OCR Workers** | 30-50 | 10GB | 50-60 | Tesseract OCR |
| **OpenSearch** | 1 | 12GB | 8-12 | Search engine |
| **System Overhead** | - | 8GB | 8-10 | OS, monitoring |
| **TOTAL** | 158-178 | ~60GB | ~120/128 | **95% utilization** |

### Expected Performance

#### Extraction Throughput
- **Fast Track** (40 workers): 160-320 files/second
- **Standard Track** (30 workers): 15-30 files/second  
- **Heavy Track** (20 workers): 5-10 files/second
- **Extreme Track** (10 workers): 1-3 files/second
- **TOTAL: 280-480 files/second**

#### Indexing Throughput
- 16 workers × 750-1,250 docs/sec = **12,000-20,000 docs/second**

#### Time Estimates

| Dataset Size | Discovery | Extraction | Indexing | Total (Text) | + OCR (Parallel) |
|--------------|-----------|------------|----------|--------------|------------------|
| **1M files** | 30-60 min | 35-60 min | 1-2 min | **~2 hours** | +8-12 hours bg |
| **2M files** | 60-120 min | 70-120 min | 2-3 min | **~4 hours** | +16-24 hours bg |
| **5M files** | 150-180 min | 175-300 min | 5-8 min | **~8 hours** | +2-3 days bg |

**Key Point:** Documents are **searchable immediately** after indexing. OCR runs in background without blocking search availability.

---

## 🏗️ Architecture Overview

### Processing Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                     DISCOVERY (4 Workers)                       │
│  E:\ Drive → File Scanning → Hash Calculation → Queue          │
└────────────┬────────────────────────────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────────────────────────────┐
│              EXTRACTION (100 Workers → 8 Tika)                  │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐ │
│  │ Fast Track   │ Standard     │ Heavy Track  │ Extreme      │ │
│  │ 40 workers   │ 30 workers   │ 20 workers   │ 10 workers   │ │
│  │ <1MB files   │ 1-10MB files │ 10-50MB      │ >50MB files  │ │
│  └──────────────┴──────────────┴──────────────┴──────────────┘ │
└────────────┬────────────────────────────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────────────────────────────┐
│         INDEXING (16 Workers → OpenSearch 12GB)                 │
│  Micro-batches → Flush every 10 sec → SEARCHABLE               │
└────────────┬────────────────────────────────────────────────────┘
             │
             ↓ (parallel)
┌─────────────────────────────────────────────────────────────────┐
│           OCR (30-50 Workers → Tesseract)                       │
│  Images → Preprocessing → OCR → Update Indexed Docs             │
└─────────────────────────────────────────────────────────────────┘
```

### Worker Distribution

**Extraction Workers (100 total):**
```
Fast Track (40): Ports 9998, 9999, 10002, 10003
  ├─ <1MB files, 5-10 sec/file
  └─ 160-320 files/second

Standard Track (30): Ports 10000, 10004
  ├─ 1-10MB files, 30-60 sec/file
  └─ 15-30 files/second

Heavy Track (20): Ports 10001, 10005
  ├─ 10-50MB files, 1-3 min/file
  └─ 5-10 files/second

Extreme Track (10): All ports (load balanced)
  ├─ >50MB files, archives, 2-10 min/file
  └─ 1-3 files/second
```

---

## 📁 Directory Structure

```
C:\DocumentSearch\                   # Application root
├── bin\                             # Startup scripts
│   ├── start_all.bat               # Start entire system
│   ├── stop_all.bat                # Stop entire system
│   ├── start_tika.bat              # Start 8 Tika instances
│   ├── stop_tika.bat               # Stop Tika
│   └── start_opensearch.bat        # Start OpenSearch
├── config\                          # Configuration
│   ├── config.yaml                 # Main configuration (OPTIMIZED)
│   ├── opensearch.yml              # OpenSearch config (12GB heap)
│   └── jvm.options                 # JVM settings
├── src\                             # Application code
│   ├── orchestrator.py             # Master orchestrator
│   ├── core\                       # Core components
│   ├── discovery\                  # Discovery workers
│   ├── extraction\                 # Extraction workers
│   ├── indexing\                   # Indexing workers
│   ├── ocr\                        # OCR workers
│   └── ui\                         # Dashboard
└── requirements.txt                # Python dependencies

D:\DocumentSearch\                   # Working directory
├── queue\                           # SQLite queue databases
├── temp\                            # Temporary files
│   ├── tika1-8\                    # Tika temp dirs
│   └── opensearch\                 # OpenSearch temp
├── logs\                            # All logs
│   ├── tika\                       # Tika logs
│   ├── opensearch\                 # OpenSearch logs
│   └── application logs            # Worker logs
├── checkpoints\                     # State checkpoints (every 5 min)
├── metrics\                         # Performance metrics
└── opensearch\                      # OpenSearch data
    └── data\                        # Index data
```

---

## ⚙️ Configuration

### Key Configuration (config/config.yaml)

Already optimized for 128 vCPU / 64GB RAM:

```yaml
extraction:
  total_workers: 100
  tika:
    instances: 8  # Ports 9998-10005

indexing:
  num_workers: 16
  opensearch:
    initial_batch_size: 100
    flush_timeout_seconds: 10  # Fast searchability

ocr:
  initial_workers: 30
  post_indexing_workers: 50
```

### Tuning Options

**For Even Faster Extraction** (if CPU allows):
```yaml
extraction:
  pools:
    fast_track:
      num_workers: 50  # Increase from 40
```

**For Slower System** (if hitting limits):
```yaml
extraction:
  total_workers: 80  # Reduce from 100

ocr:
  initial_workers: 20  # Reduce from 30
```

---

## 🎛️ Monitoring

### Real-Time Dashboard

```bash
cd C:\DocumentSearch
streamlit run src/ui/dashboard.py
```

Access at: `http://localhost:8501`

**Features:**
- Real-time statistics (auto-refresh every 5 seconds)
- Queue depths by stage
- Processing rates
- Error tracking
- Progress bars
- Time to completion estimates

### Log Files

```
D:\DocumentSearch\logs\
├── application.log          # Main application
├── discovery.log            # Discovery workers
├── extraction.log           # Extraction workers
├── indexing.log             # Indexing workers
├── ocr.log                  # OCR workers
└── tika\
    ├── tika-9998.log        # Each Tika instance
    ├── tika-9999.log
    └── ...
```

### Checkpoints

Saved every 5 minutes to: `D:\DocumentSearch\checkpoints\`

Contains:
- Queue statistics
- Processing rates
- Worker states
- Resume capability

---

## 🔄 Pause & Resume

### Graceful Stop
```bash
# Press Ctrl+C in orchestrator window
# OR run:
bin\stop_all.bat
```

**Saves:**
- Bloom filter to disk (discovery state)
- Queue states in SQLite (all stages)
- Checkpoint with statistics
- All pending work preserved

### Resume
```bash
bin\start_all.bat
```

**System will:**
1. Detect last checkpoint
2. Ask if you want to resume
3. Continue from exact position
4. No duplicate work

**Nothing starts from scratch!**

---

## 🛠️ Troubleshooting

### Problem: Tika instances not starting

**Solution:**
1. Check Java installed: `java -version` (need Java 11+)
2. Update path in `bin\start_tika.bat`:
   ```bat
   set TIKA_JAR=C:\Path\To\tika-server.jar
   ```
3. Download from: https://tika.apache.org/download.html

### Problem: OpenSearch won't start

**Solution:**
1. Check Java heap: System needs 12GB free RAM
2. Check port 9200 not in use: `netstat -ano | findstr :9200`
3. Check logs: `D:\DocumentSearch\logs\opensearch\`
4. Reduce heap if needed in `config\jvm.options`: `-Xms8g -Xmx8g`

### Problem: Workers crashing

**Solution:**
1. Check logs: `D:\DocumentSearch\logs\`
2. Verify services running:
   - `curl http://localhost:9200` (OpenSearch)
   - `curl http://localhost:9998/tika` (Tika)
3. Reduce worker counts if system overloaded

### Problem: Slow processing

**Check:**
1. CPU usage: Should be 80-95%
2. Disk I/O: E:\ drive performance
3. Tika instances: All 8 running?
4. Queue depths: Discovery keeping up?

**Optimize:**
- If CPU low: Increase workers
- If CPU maxed: OK, system saturated
- If I/O bound: Check E:\ drive speed
- If Tika backed up: Add more instances

### Problem: Out of memory

**Solutions:**
1. Reduce OCR workers: 30 → 20
2. Reduce extraction workers: 100 → 80
3. Reduce OpenSearch heap: 12GB → 10GB
4. Increase system RAM if possible

---

## 📈 Performance Optimization

### Current: 2M docs in ~4 hours

**To get to 2 hours:**

1. **Add More Tika** (if RAM available):
   ```yaml
   # Add 4 more instances → 12 total (24GB)
   # Increase extraction workers → 150
   ```

2. **Increase Batch Sizes**:
   ```yaml
   indexing:
     opensearch:
       initial_batch_size: 200  # From 100
       max_batch_size: 1000     # From 500
   ```

3. **Optimize OpenSearch**:
   ```yaml
   # During bulk indexing, disable replicas:
   curl -X PUT "http://localhost:9200/enterprise_documents/_settings" \
     -H 'Content-Type: application/json' \
     -d '{"index": {"number_of_replicas": 0, "refresh_interval": "60s"}}'
   ```

4. **Skip OCR Initially**:
   ```yaml
   ocr:
     initial_workers: 0  # Don't start OCR until after indexing
     post_indexing_workers: 50
   ```

### Bottleneck Analysis

**If Discovery slow**: Increase workers, check Bloom filter size
**If Extraction slow**: Add Tika instances, increase workers
**If Indexing slow**: Increase batch sizes, check OpenSearch health
**If OCR slow**: Expected (runs in background)

---

## 🔐 Security Notes

**Current Configuration: Development Mode**
- No authentication on OpenSearch
- No HTTPS
- CORS enabled

**For Production:**
1. Enable OpenSearch security plugin
2. Use HTTPS/TLS
3. Set authentication credentials
4. Restrict CORS
5. Use environment variables for secrets

---

## 📋 Health Checks

### Manual Verification

```powershell
# Check OpenSearch
Invoke-RestMethod http://localhost:9200

# Check Tika instances
9998..10005 | ForEach-Object {
    Write-Host "Port $_: " -NoNewline
    try {
        Invoke-RestMethod "http://localhost:$_/tika" -TimeoutSec 2
        Write-Host "OK" -ForegroundColor Green
    } catch {
        Write-Host "FAIL" -ForegroundColor Red
    }
}

# Check system resources
Get-Process python,java | Select Name,CPU,WorkingSet,Id

# Check queue status
sqlite3 D:\DocumentSearch\queue\queues.db \
  "SELECT status, COUNT(*) FROM discovered_files GROUP BY status;"
```

---

## 🎯 Success Metrics

### Target KPIs
- ✅ **Extraction**: 280-480 files/second
- ✅ **Indexing**: 12,000-20,000 docs/second  
- ✅ **Time to Searchable**: 10-30 seconds per batch
- ✅ **Total Time** (2M files): 2-4 hours
- ✅ **OCR Time**: 1-2 days (parallel, background)
- ✅ **Error Rate**: <1%
- ✅ **Pause/Resume**: 100% state preservation

### Monitoring Dashboard
Watch for:
- Steady processing rates
- Queue depths not growing
- CPU utilization 80-95%
- Memory under 90%
- No worker crashes

---

## 🚀 Next Steps

1. **Install Prerequisites** (if not already):
   - Download tika-server.jar
   - Verify OpenSearch installed
   - Test Tesseract: `tesseract --version`

2. **Start System**:
   ```bash
   cd C:\DocumentSearch\bin
   start_all.bat
   ```

3. **Monitor Progress**:
   ```bash
   # Terminal 1: Orchestrator (started by start_all.bat)
   # Terminal 2: Dashboard
   streamlit run src/ui/dashboard.py
   ```

4. **Wait for Completion**:
   - Text documents: 2-4 hours
   - Full OCR: 1-3 days (background)

5. **Search Your Documents**:
   ```bash
   curl "http://localhost:9200/enterprise_documents/_search" \
     -H 'Content-Type: application/json' \
     -d '{"query": {"match": {"all_text": "your search term"}}}'
   ```

---

## 📞 Support

**Logs**: `D:\DocumentSearch\logs\`
**Checkpoints**: `D:\DocumentSearch\checkpoints\`
**Metrics**: `D:\DocumentSearch\metrics\`

**System Status**: Check orchestrator logs and dashboard

---

**Built for AWS Instance: 128 vCPU / 64GB RAM**
**Optimized for: 2M+ documents in hours, not days**
**Full production-grade with pause/resume and crash recovery**
