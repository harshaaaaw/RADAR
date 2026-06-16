# Enterprise Document Search System

**High-Performance Document Indexing & Search Platform**

Optimized for AWS 128 vCPU / 64GB RAM instances. Process 2M documents in 2-4 hours with full OCR support.

---

## 🚀 Quick Start

### Prerequisites
- Windows Server 2022
- Java 11+
- Python 3.10+
- OpenSearch 2.x
- Apache Tika 2.9.x
- Tesseract OCR 5.x
- NSSM (Windows Service Manager)

### Installation & First Run

1. **Start required services:**
   ```powershell
   cd bin
   .\start_opensearch.bat
   .\start_tika.bat
   ```
   Wait ~60 seconds for services to fully start.

2. **Check all services are running:**
   ```powershell
   cd ..
   python src/main.py check
   ```
   This will verify OpenSearch, Tika, and Tesseract are ready.

3. **Initialize the system (first time only):**
   ```powershell
   python src/main.py init
   ```

4. **Start processing documents:**
   ```powershell
   python src/main.py start
   ```

5. **Open the dashboard (in a new terminal):**
   ```powershell
   streamlit run src/ui/dashboard.py
   ```
   Visit: http://localhost:8501

**⚠️ Troubleshooting:** If you encounter errors, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

---

## 📊 Performance Specifications

| Metric | Value |
|--------|-------|
| **Extraction Throughput** | 245-420 files/second |
| **Indexing Throughput** | 12,000-20,000 docs/second |
| **Time-to-Searchable** | 10-30 seconds |
| **Total Workers** | 150+ parallel processes |
| **OpenSearch Heap** | 12GB |
| **Tika Instances** | 7 servers @ 2GB each |
| **OCR Workers** | 30-50 (Tesseract) |

**Expected Time for 2M Documents:** 2-4 hours

---

## 🏗️ Architecture

```
Discovery (4 workers)
    ↓
Extraction (100 workers → 7 Tika instances)
    ↓
Indexing (16 workers → OpenSearch 12GB)
    ↓ (parallel)
OCR (30-50 workers → Tesseract)
```

**Key Features:**
- ✅ Size-based routing (fast/standard/heavy/extreme tracks)
- ✅ Express lane for priority files (<1MB)
- ✅ Micro-batch indexing (10-30 sec time-to-searchable)
- ✅ Background OCR (doesn't block search)
- ✅ Bloom filter deduplication
- ✅ SQLite ACID queues with persistence
- ✅ Pause/resume capability
- ✅ Health monitoring & crash recovery

---

## 📁 Project Structure

```
C:\DocumentSearch\
├── bin/                    # Startup/shutdown scripts
│   ├── start_all.bat       # Master startup
│   ├── stop_all.bat        # Master shutdown
│   ├── setup_services.bat  # Service installation
│   ├── start_opensearch.bat
│   └── start_tika.bat
├── config/
│   ├── config.yaml         # Main configuration
│   ├── opensearch.yml      # OpenSearch settings
│   └── jvm.options         # JVM heap settings
├── src/
│   ├── orchestrator.py     # Master coordinator
│   ├── main.py            # Legacy entry point
│   ├── core/              # Queue, config, logging
│   ├── discovery/         # File discovery workers
│   ├── extraction/        # Tika extraction workers
│   ├── indexing/          # OpenSearch indexing workers
│   ├── ocr/              # Tesseract OCR workers
│   ├── ui/               # Streamlit dashboard
│   └── utils/            # Bloom filter, helpers
├── requirements.txt
├── README.md
├── README_PRODUCTION.md   # Detailed operations guide
├── INSTALLATION_GUIDE.md  # Step-by-step setup
├── BUILD_COMPLETE.md      # Build summary
└── LICENSE

Data directories (created at runtime):
D:\DocumentSearch\
├── opensearch\data\       # OpenSearch indices
├── logs\                  # All component logs
├── temp\                  # Temporary processing files
└── checkpoints\           # State snapshots (every 5 min)
```

---

## 🔧 Configuration

Main configuration: `config/config.yaml`

**Key Settings:**
- **Discovery:** Root paths, file filters, exclusions
- **Extraction:** 100 workers across 4 pools, 7 Tika instances
- **Indexing:** 16 workers, batch sizes, timeouts
- **OCR:** 30-50 workers, Tesseract settings, preprocessing

---

## 📈 Monitoring

### Real-Time Dashboard
```powershell
streamlit run src/ui/dashboard.py
```
- Queue depths by stage
- Processing rates (files/sec, docs/sec)
- Worker health status
- Error tracking
- Progress estimation

### Logs
- **Orchestrator:** `D:\DocumentSearch\logs\orchestrator.log`
- **OpenSearch:** `D:\DocumentSearch\logs\opensearch\`
- **Tika:** `D:\DocumentSearch\logs\tika\`
- **Workers:** `D:\DocumentSearch\logs\workers\`

### Health Checks
```powershell
# OpenSearch
curl http://localhost:9200

# Tika instances
curl http://localhost:9998
curl http://localhost:9999
# ... (10000, 10002-10005)

# Services
Get-Service | Where-Object {$_.Name -like "*Tika*" -or $_.Name -eq "OpenSearch2"}
```

---

## 🛑 Operations

### Start System
```powershell
# As administrator
cd C:\DocumentSearch\bin
.\start_all.bat
```

### Stop System
```powershell
# Graceful shutdown with checkpoint
.\stop_all.bat
```

### Resume After Stop
```powershell
# Automatically resumes from last checkpoint
.\start_all.bat
```

### View Progress
```powershell
# Open dashboard
streamlit run src/ui/dashboard.py
```

---

## 🔍 Troubleshooting

### Services Won't Start
- Ensure running as administrator
- Check Windows Event Viewer for service errors
- Verify Java/Python in PATH

### Port Conflicts
- Check `netstat -ano | findstr :9200` (OpenSearch)
- Check `netstat -ano | findstr :9998` (Tika)
- Stop conflicting services

### Out of Memory
- Reduce worker counts in `config/config.yaml`
- Reduce OpenSearch heap in `config/jvm.options`
- Check system RAM usage: `Get-Counter '\Memory\Available MBytes'`

### Slow Processing
- Check CPU usage: `Get-Counter '\Processor(_Total)\% Processor Time'`
- Check disk I/O
- Review logs for bottlenecks
- Increase worker counts if CPU < 80%

---

## 📖 Documentation

- **[README_PRODUCTION.md](README_PRODUCTION.md)** - Complete production operations guide
- **[INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md)** - Detailed setup instructions
- **[BUILD_COMPLETE.md](BUILD_COMPLETE.md)** - System build summary

---

## 📝 License

MIT License - See [LICENSE](LICENSE) file for details

---

## 🤝 Support

For issues or questions:
1. Check logs in `D:\DocumentSearch\logs\`
2. Review [README_PRODUCTION.md](README_PRODUCTION.md) troubleshooting section
3. Verify all services running: `Get-Service | Where-Object {$_.Name -like "*Tika*"}`

---

**Built for enterprise-scale document processing with AWS infrastructure**
