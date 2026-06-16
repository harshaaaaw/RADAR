# SIMPLE STARTUP GUIDE

## 🚀 How to Start the System

### Prerequisites Check
Make sure these are running in separate terminals:

1. **OpenSearch** (Terminal 1)
   ```powershell
   cd C:\Users\DELL\Downloads\opensearch-2.14.0-windows-x64\opensearch-2.14.0\bin
   .\opensearch.bat
   ```
   Wait ~60 seconds for "Node started"

2. **Tika Servers** (Terminal 2)
   ```powershell
   cd C:\Users\DELL\Downloads\DocumentSearch\DocumentSearch
   $env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-25.0.2.10-hotspot"
   $env:Path += ";C:\Program Files\Eclipse Adoptium\jdk-25.0.2.10-hotspot\bin"
   
   Start-Process java -ArgumentList "-Xmx1024m","-jar","tika\tika-server-2.9.2.jar","--port","9998" -WindowStyle Minimized
   Start-Sleep -Seconds 2
   Start-Process java -ArgumentList "-Xmx1024m","-jar","tika\tika-server-2.9.2.jar","--port","9999" -WindowStyle Minimized
   ```
   Wait ~10 seconds

---

## ✨ EASY WAY - Use the Startup Script

### Terminal 3: Start Document Search System
```powershell
cd C:\Users\DELL\Downloads\DocumentSearch\DocumentSearch
.\start-system.ps1
```

This will:
- Set Java environment automatically
- Wait for database locks to release
- Start the document processing system
- Discover and process all 502 files

---

## 📊 Optional: Start Dashboard

### Terminal 4: Start Dashboard (Optional)
```powershell
cd C:\Users\DELL\Downloads\DocumentSearch\DocumentSearch
.\start-dashboard.ps1
```

Opens web interface at: http://localhost:8501

---

## 🔧 Manual Way (If Scripts Don't Work)

### Terminal 3: Manual Start
```powershell
cd C:\Users\DELL\Downloads\DocumentSearch\DocumentSearch
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-25.0.2.10-hotspot"
$env:Path += ";C:\Program Files\Eclipse Adoptium\jdk-25.0.2.10-hotspot\bin"
python src/main.py start
```

### Terminal 4: Manual Dashboard
```powershell
cd C:\Users\DELL\Downloads\DocumentSearch\DocumentSearch
python -m streamlit run src/ui/dashboard.py
```

---

## ✅ What You Should See

### In Terminal 3 (Document Search):
```
Spawning 1 discovery workers...
  Started discovery-1 (PID: XXXX)
[Discovery-1] Scanned: 10 | New: 10 (100%)
[Discovery-1] Scanned: 50 | New: 50 (100%)
...
Files Discovered: 502
New Files Queued: 502
```

Then extraction and indexing will process all files!

---

## 📁 Files Created

- **`start-system.ps1`** - Easy startup for document search
- **`start-dashboard.ps1`** - Easy startup for dashboard
- **`SIMPLE_START.md`** - This guide

---

## 🎯 Quick Commands

```powershell
# Start the system (easiest way)
.\start-system.ps1

# Start the dashboard (optional)
.\start-dashboard.ps1

# Check if OpenSearch is running
curl http://localhost:9200

# Check if Tika is running
curl http://localhost:9998/tika
curl http://localhost:9999/tika
```

---

**Use `.\start-system.ps1` to start processing your 502 test files!** 🚀
