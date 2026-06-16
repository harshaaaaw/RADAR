# 🚀 **AWS WINDOWS DEPLOYMENT GUIDE**

**System:** AWS EC2 Windows Server (64 vCPU / 256GB RAM)  
**Current Setup:** 7 Tika servers + OpenSearch running as NSSM services  
**Goal:** Deploy optimized configuration for production

---

## 📋 **PREREQUISITES**

### **What You Already Have:**
- ✅ AWS Windows Server instance (64 vCPU / 256GB RAM)
- ✅ 7 Tika servers running as NSSM services
- ✅ OpenSearch 2.x running as NSSM service
- ✅ NSSM (Non-Sucking Service Manager) installed
- ✅ Java installed (for Tika)
- ✅ Python installed

### **What You Need to Install:**
- [ ] Tesseract OCR
- [ ] Poppler (for PDF processing)
- [ ] Redis (for queue management)
- [ ] Python dependencies
- [ ] SpaCy NLP model (optional but recommended)

---

## 🎯 **DEPLOYMENT OVERVIEW**

### **Current vs Optimized:**

| Component | Current | Optimized | Change |
|-----------|---------|-----------|--------|
| **Tika Servers** | 7 × 2GB | 12 × 8-12GB | +5 servers, 4-6x RAM each |
| **OpenSearch Heap** | 12GB | 64GB | 5.3x increase |
| **Extraction Workers** | 24 | 40 | +16 workers |
| **OCR Workers** | 28 initial | 4 initial | -24 (reduce competition) |
| **Config File** | config.yaml | config_aws.yaml | New optimized config |

---

## 📁 **STEP 1: PREPARE THE SYSTEM**

### **1.1 Create Directory Structure**

```powershell
# Create base directories
New-Item -ItemType Directory -Force -Path "D:\DocumentSearch"
New-Item -ItemType Directory -Force -Path "D:\DocumentSearch\queue"
New-Item -ItemType Directory -Force -Path "D:\DocumentSearch\temp"
New-Item -ItemType Directory -Force -Path "D:\DocumentSearch\logs"
New-Item -ItemType Directory -Force -Path "D:\DocumentSearch\checkpoints"
New-Item -ItemType Directory -Force -Path "D:\DocumentSearch\metrics"
New-Item -ItemType Directory -Force -Path "D:\DocumentSearch\backup"
New-Item -ItemType Directory -Force -Path "D:\DocumentSearch\opensearch"

# Create Tika temp directories (12 servers)
1..14 | ForEach-Object {
    New-Item -ItemType Directory -Force -Path "D:\DocumentSearch\temp\tika$_"
}
```

### **1.2 Install Missing Dependencies**

**Install Tesseract OCR:**
```powershell
# Download from: https://github.com/UB-Mannheim/tesseract/wiki
# Install to: C:\Program Files\Tesseract-OCR
# Add to PATH
```

**Install Poppler:**
```powershell
# Download from: https://github.com/oschwartz10612/poppler-windows/releases
# Extract to: C:\poppler
# Add C:\poppler\Library\bin to PATH
```

**Install Redis:**
```powershell
# Download from: https://github.com/microsoftarchive/redis/releases
# Install as Windows service
# Or use: choco install redis-64
```

**Install Python Dependencies:**
```powershell
cd C:\DocumentSearch
pip install -r requirements.txt
```

**Install SpaCy Model (Optional but Recommended):**
```powershell
python -m spacy download en_core_web_lg
```

---

## 🔧 **STEP 2: STOP EXISTING SERVICES**

### **2.1 Stop All Current Services**

```powershell
# Stop Tika services
nssm stop TikaServer1
nssm stop TikaServer2
nssm stop TikaServer3
nssm stop TikaServer4
nssm stop TikaServer5
nssm stop TikaServer6
nssm stop TikaServer7

# Stop OpenSearch
nssm stop OpenSearch2

# Verify all stopped
Get-Service | Where-Object {$_.Name -like "Tika*" -or $_.Name -like "OpenSearch*"}
```

---

## 📝 **STEP 3: UPDATE OPENSEARCH CONFIGURATION**

### **3.1 Backup Current Config**

```powershell
# Backup existing config
Copy-Item "C:\opensearch-2.14.0\config\opensearch.yml" `
          "C:\opensearch-2.14.0\config\opensearch.yml.backup"
Copy-Item "C:\opensearch-2.14.0\config\jvm.options" `
          "C:\opensearch-2.14.0\config\jvm.options.backup"
```

### **3.2 Deploy New OpenSearch Config**

```powershell
# Copy optimized configs
Copy-Item "C:\DocumentSearch\config\opensearch_aws.yml" `
          "C:\opensearch-2.14.0\config\opensearch.yml" -Force
Copy-Item "C:\DocumentSearch\config\jvm_aws.options" `
          "C:\opensearch-2.14.0\config\jvm.options" -Force
```

### **3.3 Update Paths in opensearch.yml**

**Edit:** `C:\opensearch-2.14.0\config\opensearch.yml`

```yaml
# Update these paths for Windows:
path.data: ["D:\\DocumentSearch\\opensearch\\data"]
path.logs: "D:\\DocumentSearch\\opensearch\\logs"
```

### **3.4 Update Paths in jvm.options**

**Edit:** `C:\opensearch-2.14.0\config\jvm.options`

```
# Update log paths for Windows:
-Xlog:gc*,gc+age=trace,safepoint:file=D:/DocumentSearch/logs/opensearch/gc.log:utctime,pid,tags:filecount=10,filesize=100m
-Djava.io.tmpdir=D:/DocumentSearch/temp/opensearch
-XX:HeapDumpPath=D:/DocumentSearch/logs/opensearch/heapdump.hprof
-XX:ErrorFile=D:/DocumentSearch/logs/opensearch/hs_err_pid%p.log
```

### **3.5 Verify Heap Size**

**Check:** `C:\opensearch-2.14.0\config\jvm.options`

```
-Xms64g  # Should be 64GB (not 12GB)
-Xmx64g  # Should be 64GB (not 12GB)
```

---

## 🔥 **STEP 4: UPDATE TIKA SERVICES**

### **4.1 Remove Old Tika Services**

```powershell
# Remove old services
nssm remove TikaServer1 confirm
nssm remove TikaServer2 confirm
nssm remove TikaServer3 confirm
nssm remove TikaServer4 confirm
nssm remove TikaServer5 confirm
nssm remove TikaServer6 confirm
nssm remove TikaServer7 confirm
```

### **4.2 Create New Tika Services (12 servers)**

**Create this script:** `install-tika-services.ps1`

```powershell
# Tika Server Installation Script for AWS
# 12 servers with 8-12GB RAM each

$javaPath = "C:\Program Files\Java\jdk-17\bin\java.exe"
$tikaJar = "C:\DocumentSearch\tika\tika-server-2.9.2.jar"

# Fast track (4 servers × 8GB)
@(
    @{Port=9998; Memory=8192; Name="TikaFast1"},
    @{Port=9999; Memory=8192; Name="TikaFast2"},
    @{Port=10000; Memory=8192; Name="TikaFast3"},
    @{Port=10001; Memory=8192; Name="TikaFast4"}
) | ForEach-Object {
    Write-Host "Installing $($_.Name) on port $($_.Port) with $($_.Memory)MB RAM..."
    nssm install $_.Name $javaPath "-Xmx$($_.Memory)m" "-jar" $tikaJar "--port" $_.Port
    nssm set $_.Name AppDirectory "C:\DocumentSearch\tika"
    nssm set $_.Name DisplayName "Tika Server - $($_.Name)"
    nssm set $_.Name Description "Apache Tika Server (Fast Track) - Port $($_.Port)"
    nssm set $_.Name Start SERVICE_AUTO_START
}

# Standard track (4 servers × 8GB)
@(
    @{Port=10002; Memory=8192; Name="TikaStd1"},
    @{Port=10003; Memory=8192; Name="TikaStd2"},
    @{Port=10004; Memory=8192; Name="TikaStd3"},
    @{Port=10005; Memory=8192; Name="TikaStd4"}
) | ForEach-Object {
    Write-Host "Installing $($_.Name) on port $($_.Port) with $($_.Memory)MB RAM..."
    nssm install $_.Name $javaPath "-Xmx$($_.Memory)m" "-jar" $tikaJar "--port" $_.Port
    nssm set $_.Name AppDirectory "C:\DocumentSearch\tika"
    nssm set $_.Name DisplayName "Tika Server - $($_.Name)"
    nssm set $_.Name Description "Apache Tika Server (Standard Track) - Port $($_.Port)"
    nssm set $_.Name Start SERVICE_AUTO_START
}

# Heavy track (2 servers × 10GB)
@(
    @{Port=10006; Memory=10240; Name="TikaHeavy1"},
    @{Port=10007; Memory=10240; Name="TikaHeavy2"}
) | ForEach-Object {
    Write-Host "Installing $($_.Name) on port $($_.Port) with $($_.Memory)MB RAM..."
    nssm install $_.Name $javaPath "-Xmx$($_.Memory)m" "-jar" $tikaJar "--port" $_.Port
    nssm set $_.Name AppDirectory "C:\DocumentSearch\tika"
    nssm set $_.Name DisplayName "Tika Server - $($_.Name)"
    nssm set $_.Name Description "Apache Tika Server (Heavy Track) - Port $($_.Port)"
    nssm set $_.Name Start SERVICE_AUTO_START
}

# Extreme track (2 servers × 12GB)
@(
    @{Port=10008; Memory=12288; Name="TikaExtreme1"},
    @{Port=10009; Memory=12288; Name="TikaExtreme2"}
) | ForEach-Object {
    Write-Host "Installing $($_.Name) on port $($_.Port) with $($_.Memory)MB RAM..."
    nssm install $_.Name $javaPath "-Xmx$($_.Memory)m" "-jar" $tikaJar "--port" $_.Port
    nssm set $_.Name AppDirectory "C:\DocumentSearch\tika"
    nssm set $_.Name DisplayName "Tika Server - $($_.Name)"
    nssm set $_.Name Description "Apache Tika Server (Extreme Track) - Port $($_.Port)"
    nssm set $_.Name Start SERVICE_AUTO_START
}

Write-Host "`n✅ All 12 Tika services installed!"
Write-Host "Run 'Get-Service Tika*' to verify"
```

**Run the script:**
```powershell
.\install-tika-services.ps1
```

---

## 🗄️ **STEP 5: SETUP REDIS SERVICE**

### **5.1 Install Redis as Service**

```powershell
# If using Redis MSI installer, it creates service automatically
# If using zip, create service:

$redisPath = "C:\Redis\redis-server.exe"
$redisConfig = "C:\Redis\redis.windows.conf"

nssm install Redis $redisPath $redisConfig
nssm set Redis DisplayName "Redis Server"
nssm set Redis Description "Redis in-memory data store"
nssm set Redis Start SERVICE_AUTO_START
```

---

## 📦 **STEP 6: DEPLOY DOCUMENT SEARCH SYSTEM**

### **6.1 Copy Files to AWS**

```powershell
# Copy your DocumentSearch folder to AWS
# Recommended location: C:\DocumentSearch
```

### **6.2 Update config_aws.yaml Paths**

**Edit:** `C:\DocumentSearch\config\config_aws.yaml`

```yaml
# Update paths for Windows:
paths:
  source_drive: "E:\\FileNet_Data_Extracts\\US_Archive_Extract\\2013\\201301"
  working_root: "D:\\DocumentSearch"
  queue_db: "D:\\DocumentSearch\\queue"
  temp_dir: "D:\\DocumentSearch\\temp"
  logs_dir: "D:\\DocumentSearch\\logs"
  checkpoints_dir: "D:\\DocumentSearch\\checkpoints"
  metrics_dir: "D:\\DocumentSearch\\metrics"
  backup_dir: "D:\\DocumentSearch\\backup"
  app_root: "C:\\DocumentSearch"

# Update Tika temp directories:
extraction:
  tika:
    instances:
      - host: "localhost"
        port: 9998
        memory_mb: 8192
        temp_dir: "D:\\DocumentSearch\\temp\\tika1"
      # ... (update all 12 instances)
```

### **6.3 Update OCR Paths**

**Edit:** `C:\DocumentSearch\config\config_aws.yaml`

```yaml
ocr:
  poppler_path: "C:\\poppler\\Library\\bin"
  tesseract:
    command: "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
    datapath: "C:\\Program Files\\Tesseract-OCR\\tessdata"
```

---

## 🚀 **STEP 7: START SERVICES**

### **7.1 Start in Correct Order**

```powershell
# 1. Start Redis
Start-Service Redis
Start-Sleep -Seconds 5

# 2. Start OpenSearch
Start-Service OpenSearch2
Start-Sleep -Seconds 30

# 3. Verify OpenSearch is ready
curl http://localhost:9200/_cluster/health

# 4. Start all Tika servers
Get-Service Tika* | Start-Service
Start-Sleep -Seconds 10

# 5. Verify Tika servers
9998,9999,10000,10001,10002,10003,10004,10005,10006,10007,10008,10009 | ForEach-Object {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$_/tika" -UseBasicParsing
        Write-Host "✅ Tika on port $_ is running"
    } catch {
        Write-Host "❌ Tika on port $_ is NOT running"
    }
}
```

---

## 📊 **STEP 8: DELETE OLD INDEX (REQUIRED FOR SEARCH FIXES)**

```powershell
# Delete old index to apply new mapping
Invoke-RestMethod -Uri "http://localhost:9200/enterprise_documents" -Method Delete
```

---

## 🎯 **STEP 9: START DOCUMENT SEARCH SYSTEM**

### **9.1 Manual Start (for testing)**

```powershell
cd C:\DocumentSearch
python src\main.py start --config config\config_aws.yaml
```

### **9.2 Create as Windows Service (Recommended)**

**Create script:** `install-docsearch-service.ps1`

```powershell
$pythonPath = "C:\Python310\python.exe"
$scriptPath = "C:\DocumentSearch\src\main.py"
$configPath = "C:\DocumentSearch\config\config_aws.yaml"

nssm install DocumentSearch $pythonPath `
    $scriptPath "start" "--config" $configPath

nssm set DocumentSearch AppDirectory "C:\DocumentSearch"
nssm set DocumentSearch DisplayName "Enterprise Document Search"
nssm set DocumentSearch Description "Document indexing and search system"
nssm set DocumentSearch Start SERVICE_AUTO_START

# Set dependencies (start after Redis, OpenSearch, Tika)
nssm set DocumentSearch DependOnService Redis OpenSearch2

Write-Host "✅ DocumentSearch service installed!"
Write-Host "Start with: Start-Service DocumentSearch"
```

**Run:**
```powershell
.\install-docsearch-service.ps1
Start-Service DocumentSearch
```

---

## ✅ **STEP 10: VERIFY DEPLOYMENT**

### **10.1 Check All Services**

```powershell
# Check service status
Get-Service Redis, OpenSearch2, Tika*, DocumentSearch | 
    Select-Object Name, Status, DisplayName | 
    Format-Table -AutoSize
```

### **10.2 Check System Status**

```powershell
# Check document search status
python src\main.py status

# Expected output:
# Discovery Workers:   8/8 running
# Extraction Workers:  40/40 running
# Indexing Workers:    10/10 running
# OCR Workers:         4/4 running
```

### **10.3 Check Resource Usage**

```powershell
# Check memory usage
Get-Process java, python, redis-server | 
    Select-Object Name, @{N='Memory(GB)';E={[math]::Round($_.WS/1GB,2)}} |
    Format-Table -AutoSize

# Expected:
# - OpenSearch: ~64GB
# - Tika servers: ~100GB total
# - Python workers: ~40GB
# - Total: ~200GB
```

### **10.4 Check OpenSearch Health**

```powershell
# Cluster health
Invoke-RestMethod -Uri "http://localhost:9200/_cluster/health?pretty"

# Heap usage
Invoke-RestMethod -Uri "http://localhost:9200/_nodes/stats/jvm?pretty" | 
    Select-Object -ExpandProperty nodes | 
    Select-Object -First 1 -ExpandProperty jvm | 
    Select-Object -ExpandProperty mem

# Expected heap_max_in_bytes: 68719476736 (64GB)
```

---

## 🔍 **STEP 11: TEST SEARCH**

### **11.1 Test API**

```powershell
# Test search endpoint
Invoke-RestMethod -Uri "http://localhost:8080/search?q=test&size=5" | ConvertTo-Json -Depth 5
```

### **11.2 Test Long Sentence (Should NOT Error)**

```powershell
$longQuery = "This is a very long search query with many words to test that the system handles long sentences without throwing nested items errors or any other query parsing errors"

Invoke-RestMethod -Uri "http://localhost:8080/search?q=$longQuery&size=5"
# Expected: Results returned, no error
```

---

## 📝 **STEP 12: MONITORING**

### **12.1 Create Monitoring Script**

**Create:** `monitor-system.ps1`

```powershell
while ($true) {
    Clear-Host
    Write-Host "=== SYSTEM MONITOR ===" -ForegroundColor Cyan
    Write-Host "Time: $(Get-Date)" -ForegroundColor Gray
    
    # Services
    Write-Host "`n--- Services ---" -ForegroundColor Yellow
    Get-Service Redis, OpenSearch2, DocumentSearch | 
        Select-Object Name, Status | Format-Table -AutoSize
    
    # Memory
    Write-Host "--- Memory Usage ---" -ForegroundColor Yellow
    $totalMem = (Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB
    $freeMem = (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB
    $usedMem = $totalMem - $freeMem
    Write-Host "Total: $([math]::Round($totalMem,2)) GB"
    Write-Host "Used:  $([math]::Round($usedMem,2)) GB ($([math]::Round($usedMem/$totalMem*100,1))%)"
    Write-Host "Free:  $([math]::Round($freeMem,2)) GB"
    
    # Processes
    Write-Host "`n--- Top Processes ---" -ForegroundColor Yellow
    Get-Process java, python, redis-server -ErrorAction SilentlyContinue | 
        Select-Object Name, @{N='Memory(GB)';E={[math]::Round($_.WS/1GB,2)}}, CPU | 
        Sort-Object -Property 'Memory(GB)' -Descending | 
        Format-Table -AutoSize
    
    Start-Sleep -Seconds 5
}
```

**Run:**
```powershell
.\monitor-system.ps1
```

---

## 🚨 **TROUBLESHOOTING**

### **Issue: OpenSearch Won't Start**

```powershell
# Check logs
Get-Content "D:\DocumentSearch\opensearch\logs\*.log" -Tail 50

# Common fix: Memory lock
# Edit opensearch.yml:
bootstrap.memory_lock: false  # Set to false on Windows
```

### **Issue: Tika Servers Crash**

```powershell
# Check if ports are in use
9998..10009 | ForEach-Object {
    $port = $_
    $conn = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($conn) {
        Write-Host "Port $port is in use by PID $($conn.OwningProcess)"
    }
}

# Check Tika logs
Get-Content "D:\DocumentSearch\logs\hs_err_*.log" -Tail 100
```

### **Issue: Workers Not Starting**

```powershell
# Check Python logs
Get-Content "D:\DocumentSearch\logs\orchestrator.log" -Tail 50

# Check Redis connection
redis-cli ping
# Expected: PONG
```

---

## 📊 **EXPECTED PERFORMANCE**

| Metric | Value |
|--------|-------|
| **Indexing Speed** | 500-1000 files/sec |
| **CPU Usage** | 75-85% |
| **RAM Usage** | ~200GB (80%) |
| **Tika Stability** | 24/7 stable |
| **1M files** | 30-60 minutes |

---

## 🎯 **QUICK REFERENCE**

### **Service Management**

```powershell
# Start all
Start-Service Redis, OpenSearch2
Get-Service Tika* | Start-Service
Start-Service DocumentSearch

# Stop all
Stop-Service DocumentSearch
Get-Service Tika* | Stop-Service
Stop-Service OpenSearch2, Redis

# Restart all
Restart-Service Redis, OpenSearch2
Get-Service Tika* | Restart-Service
Restart-Service DocumentSearch
```

### **Check Status**

```powershell
# System status
python src\main.py status

# OpenSearch health
curl http://localhost:9200/_cluster/health?pretty

# Tika health
9998..10009 | ForEach-Object { curl "http://localhost:$_/tika" }
```

---

## ✅ **DEPLOYMENT CHECKLIST**

- [ ] All directories created
- [ ] Dependencies installed (Tesseract, Poppler, Redis)
- [ ] OpenSearch config updated (64GB heap)
- [ ] 12 Tika services created and running
- [ ] Redis service running
- [ ] Old index deleted
- [ ] config_aws.yaml paths updated for Windows
- [ ] Document search system started
- [ ] All services verified running
- [ ] Resource usage verified (~200GB RAM)
- [ ] Search tested (no errors)

---

**Status:** ✅ **READY FOR AWS WINDOWS DEPLOYMENT**

**Estimated Setup Time:** 2-3 hours  
**Estimated Re-indexing Time:** Varies by data size

**Support:** Check logs in `D:\DocumentSearch\logs\` for any issues
