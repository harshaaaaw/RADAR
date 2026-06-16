# QUICK FIX - OpenSearch Not Running

## ❌ Problem
OpenSearch is not running! The workers can't connect to port 9200.

## ✅ Solution

### Step 1: Start OpenSearch

Open a **new terminal** and run:

```powershell
cd C:\Users\DELL\Downloads\opensearch-2.14.0-windows-x64\opensearch-2.14.0\bin
.\opensearch.bat
```

**Wait ~60 seconds** for OpenSearch to start. Look for:
- "Node started"
- "Cluster health status changed from RED to GREEN"

### Step 2: Verify OpenSearch is Running

In another terminal:
```powershell
curl http://localhost:9200
```

Should return JSON with version info.

### Step 3: Restart the Document Search System

Once OpenSearch is running, restart the system:

```powershell
cd C:\Users\DELL\Downloads\DocumentSearch\DocumentSearch
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-25.0.2.10-hotspot"
$env:Path += ";C:\Program Files\Eclipse Adoptium\jdk-25.0.2.10-hotspot\bin"
python src/main.py start
```

---

## 📋 Complete Startup Sequence

For future reference, always start in this order:

### Terminal 1: OpenSearch
```powershell
cd C:\Users\DELL\Downloads\opensearch-2.14.0-windows-x64\opensearch-2.14.0\bin
.\opensearch.bat
```
Wait ~60 seconds

### Terminal 2: Tika Servers
```powershell
cd C:\Users\DELL\Downloads\DocumentSearch\DocumentSearch
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-25.0.2.10-hotspot"
$env:Path += ";C:\Program Files\Eclipse Adoptium\jdk-25.0.2.10-hotspot\bin"

Start-Process java -ArgumentList "-Xmx1024m","-jar","tika\tika-server-2.9.2.jar","--port","9998" -WindowStyle Minimized
Start-Sleep -Seconds 2
Start-Process java -ArgumentList "-Xmx1024m","-jar","tika\tika-server-2.9.2.jar","--port","9999" -WindowStyle Minimized
```
Wait ~10 seconds

### Terminal 3: Document Search System
```powershell
cd C:\Users\DELL\Downloads\DocumentSearch\DocumentSearch
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-25.0.2.10-hotspot"
$env:Path += ";C:\Program Files\Eclipse Adoptium\jdk-25.0.2.10-hotspot\bin"
python src/main.py start
```

### Terminal 4: Dashboard (Optional)
```powershell
cd C:\Users\DELL\Downloads\DocumentSearch\DocumentSearch
python -m streamlit run src/ui/dashboard.py
```

---

## 🔍 How to Check What's Running

```powershell
# Check OpenSearch
curl http://localhost:9200

# Check Tika servers
curl http://localhost:9998/tika
curl http://localhost:9999/tika

# Check running Java processes
Get-Process java
```

---

## ⚠️ Common Issues

### OpenSearch won't start
- Check if port 9200 is already in use
- Make sure you disabled security in opensearch.yml
- Check logs in opensearch/logs/

### Tika won't start
- Make sure Java is in PATH
- Check if ports 9998/9999 are available
- Verify tika-server-2.9.2.jar exists

### System errors
- Make sure OpenSearch is running FIRST
- Make sure Tika servers are running
- Then start the document search system

---

**Start OpenSearch first, then everything else will work!** 🚀
