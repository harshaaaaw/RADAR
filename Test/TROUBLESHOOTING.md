# Troubleshooting Guide

## Prerequisites Check

Before running the system, ensure these are installed:

### Required Software

1. **Python 3.10+**
   ```powershell
   python --version
   # Should show: Python 3.10.x or higher
   ```

2. **Java 11+** (for OpenSearch and Tika)
   ```powershell
   java -version
   # Should show: version "11" or higher
   ```

3. **OpenSearch 2.x**
   - Download: https://opensearch.org/downloads.html
   - Install to: `C:\opensearch-2.12.0` (or update config)

4. **Apache Tika 2.9.x**
   - Download: https://tika.apache.org/download.html
   - Place `tika-server.jar` in `C:\Program Files\Tika\`

5. **Tesseract OCR 5.x**
   - Download: https://github.com/UB-Mannheim/tesseract/wiki
   - Install and note the installation path

6. **Python Dependencies**
   ```powershell
   pip install -r requirements.txt
   ```

### Verify All Prerequisites

Run the check command to verify everything:
```powershell
python src/main.py check
```

---

## Common Issues and Solutions

### 1. Database Locked Error

**Symptom:**
```
⚠ Queue database files locked - stop dashboard and retry
```

**Cause:** The Streamlit dashboard is still running and has an open connection to the SQLite database.

**Solution:**
1. Stop the dashboard first:
   - Press `Ctrl+C` in the terminal running the dashboard
   - Or run: `Get-Process *streamlit* | Stop-Process -Force` in PowerShell

2. Then run the reset command again:
   ```powershell
   python src/main.py reset --force
   ```

---

### 2. OpenSearch Connection Refused

**Symptom:**
```
ConnectionRefusedError: [WinError 10061] No connection could be made because the target machine actively refused it
```

**Cause:** OpenSearch is not running or failed to start.

**Common Root Causes:**
1. Service not started
2. Configuration error (see below)
3. Port 9200 already in use

**Solution:**

**Step 1: Check if OpenSearch service is running**
```powershell
sc query OpenSearch2
# Should show: STATE: 4 RUNNING
```

**Step 2: Check OpenSearch logs if service shows RUNNING but not responding**
```powershell
Get-Content "C:\opensearch-2.12.0\logs\stderr.log" -Tail 50
```

**Common Error: "node settings must not contain any index level settings"**

This means your opensearch.yml has invalid configuration. Fix by removing these lines:
```yaml
# ❌ Remove these from opensearch.yml
index.translog.durability: async
index.translog.sync_interval: 5s
index.translog.flush_threshold_size: 1gb
index.merge.scheduler.max_thread_count: 8
```

See [OPENSEARCH_FIX.md](OPENSEARCH_FIX.md) for detailed explanation.

**Step 3: Start/Restart OpenSearch**

**Option 1: Quick Start (Direct)**
```powershell
cd bin
.\start_opensearch_simple.bat
```
This starts OpenSearch directly in the terminal (no Windows Service required).

**Option 2: Windows Service (Production)**
```powershell
# Restart the service
nssm restart OpenSearch2
```

**Option 3: Manual Start**
```powershell
cd C:\opensearch-2.12.0\bin
.\opensearch.bat
```

**Verify it's running:**
Wait 30-60 seconds, then check:
```powershell
Invoke-RestMethod http://localhost:9200 | ConvertTo-Json
```

You should see OpenSearch version information.

**If OpenSearch is not installed:**
1. Download from: https://opensearch.org/downloads.html
2. Extract to `C:\opensearch-2.12.0` (or update paths in config)
3. Ensure Java 11+ is installed

---

### 3. Tika Not Running

**Symptom:**
```
✗ Tika instance on port 9998 not accessible
```

**Cause:** Tika server instances are not running.

**Solution:**
1. Start Tika servers:
   ```powershell
   cd bin
   .\start_tika.bat
   ```

2. This will start all configured Tika instances (typically 7-8 instances)

---

### 4. Check Services Before Starting

Before running the system, always check that all services are running:

```powershell
python src/main.py check
```

This will verify:
- ✓ Tika instances (all configured ports)
- ✓ OpenSearch
- ✓ Tesseract OCR

---

## Recommended Startup Sequence

1. **Start services** (from `bin` directory):
   ```powershell
   cd bin
   .\start_opensearch.bat
   .\start_tika.bat
   cd ..
   ```

2. **Wait for services** (~1 minute):
   ```powershell
   timeout /t 60
   ```

3. **Check services**:
   ```powershell
   python src/main.py check
   ```

4. **Start the system** (if all checks pass):
   ```powershell
   python src/main.py start
   ```

5. **Open dashboard** (in a separate terminal):
   ```powershell
   streamlit run src/ui/dashboard.py
   ```

---

## Complete Reset Procedure

If you need to completely reset the system:

1. **Stop all running processes**:
   ```powershell
   # Stop dashboard
   Get-Process *streamlit* | Stop-Process -Force
   
   # Stop orchestrator (if running)
   # Press Ctrl+C in the orchestrator terminal
   ```

2. **Reset the system**:
   ```powershell
   python src/main.py reset --force
   ```

3. **Restart services** (follow Recommended Startup Sequence above)

---

## Service Status Commands

### Check if OpenSearch is running:
```powershell
curl http://localhost:9200
# Or
Invoke-WebRequest http://localhost:9200
```

### Check if Tika is running:
```powershell
curl http://localhost:9998/tika
curl http://localhost:9999/tika
# ... (check all configured ports)
```

### List running Python processes:
```powershell
Get-Process python*
```

### Stop all Streamlit processes:
```powershell
Get-Process *streamlit* | Stop-Process -Force
```

---

## Port Usage

Default ports used by the system:

| Service | Ports | Purpose |
|---------|-------|---------|
| OpenSearch | 9200 | Search engine |
| Tika | 9998-10005 | Text extraction (8 instances) |
| Dashboard | 8501 | Streamlit web interface |
| API | 8080 | REST API (optional) |

**Note:** Port 10001 is typically skipped due to conflicts with Windows agentid-service.

---

## Log Files

If you encounter issues, check the log files:

```
D:\DocumentSearch\logs\
├── application.log      # Main application log
├── errors.log           # Error-only log
├── orchestrator.log     # Master orchestrator
├── discovery.log        # File discovery
├── extraction.log       # Text extraction
├── indexing.log         # Document indexing
└── ocr.log             # OCR processing
```

View logs in real-time:
```powershell
Get-Content D:\DocumentSearch\logs\application.log -Wait
```

---

## Database Location

The SQLite database is located at:
```
D:\DocumentSearch\queue\queues.db
```

**Important:** Never manually edit or delete this file while the system is running!

---

## Getting Help

1. Run service check: `python src/main.py check`
2. Check application logs: `D:\DocumentSearch\logs\application.log`
3. Review this troubleshooting guide
4. Check the main README.md for architecture details

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `python src/main.py check` | Check all services |
| `python src/main.py init` | Initialize system |
| `python src/main.py start` | Start processing |
| `python src/main.py status` | Show system status |
| `python src/main.py stats` | Detailed statistics |
| `python src/main.py reset` | Reset all data |
| `streamlit run src/ui/dashboard.py` | Open dashboard |
