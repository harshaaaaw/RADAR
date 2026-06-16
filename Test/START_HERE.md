# SIMPLE STARTUP GUIDE

## Current Status
✓ All software installed
✓ Configuration updated
✗ Services NOT running yet

## You Need to Start 2 Services:

### 1. Start OpenSearch (Terminal 1)

```powershell
cd C:\Users\DELL\Downloads\opensearch-2.14.0-windows-x64\opensearch-2.14.0\bin
.\opensearch.bat
```

**Wait ~60 seconds** until you see: "Node started"

### 2. Start Tika Servers (Terminal 2)

```powershell
cd C:\Users\DELL\Downloads\DocumentSearch\DocumentSearch

# Set Java path
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-25.0.2.10-hotspot"
$env:Path += ";C:\Program Files\Eclipse Adoptium\jdk-25.0.2.10-hotspot\bin"

# Start Tika
cd bin
.\start_tika.bat
```

This will start 7 Tika servers on ports 9998-10005

### 3. Initialize System (Terminal 3)

```powershell
cd C:\Users\DELL\Downloads\DocumentSearch\DocumentSearch

# Set Java path
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-25.0.2.10-hotspot"
$env:Path += ";C:\Program Files\Eclipse Adoptium\jdk-25.0.2.10-hotspot\bin"

# Initialize
python src/main.py init
```

### 4. Start Processing

```powershell
python src/main.py start
```

### 5. Open Dashboard (Terminal 4)

```powershell
cd C:\Users\DELL\Downloads\DocumentSearch\DocumentSearch
streamlit run src/ui/dashboard.py
```

Visit: http://localhost:8501

---

## Quick Test Commands

After starting OpenSearch and Tika, verify they're running:

```powershell
# Test OpenSearch
curl http://localhost:9200

# Test Tika
curl http://localhost:9998/tika
```

Both should return responses (not errors).

---

## Summary

You need **4 terminal windows**:
1. OpenSearch (keeps running)
2. Tika servers (keeps running)
3. Main processing (keeps running)
4. Dashboard (keeps running)

**Start them in order: OpenSearch → Tika → Init → Start → Dashboard**
